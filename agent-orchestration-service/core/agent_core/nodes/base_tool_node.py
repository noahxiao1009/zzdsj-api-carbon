# new file: nodes/base_tool_node.py (or similar name)

import logging
import copy
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


from pocketflow import AsyncNode
from pocketflow import AsyncParallelBatchNode 

logger = logging.getLogger(__name__)

class BaseToolNode(AsyncNode):
    """
    A unified base class for all custom tool nodes.
    It encapsulates standard prep and post logic, so subclasses only need to implement the core exec_async method.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self._tool_info will be automatically attached by the @tool_registry decorator
        if not hasattr(self, '_tool_info'):
            # This is a safety check to ensure the subclass is decorated correctly
            raise TypeError(f"Class {self.__class__.__name__} inherits from BaseToolNode but was not decorated with @tool_registry.")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic preparation step.
        Extracts tool parameters from state.current_action.
        """
        state = shared.get("state", {})
        current_action = state.get("current_action", {})
        
        # Extract all parameters from the action except for reserved keywords
        tool_params = {
            k: v for k, v in current_action.items() 
            if k not in ["type", "tool_name", "implementation_type", "tool_call_id"]
        }
        
        logger.debug("tool_prep_begin", extra={"tool_name": self._tool_info['name'], "tool_params": tool_params})
        
        # 工具开始时不立即更新Flow视图，避免过于频繁的更新
        # Flow视图会通过其他机制获得更新
        
        # Pass the parameters and the full context to exec_async
        return {
            "tool_params": tool_params,
            "shared_context": shared
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """
        [Abstract Method] All tool subclasses must override this method to implement their core business logic.
        
        Returns:
            Must follow the standard output contract:
            {
                "status": "success" | "error",
                "payload": Dict[str, Any],      # Core output, for the LLM
                "error_message": Optional[str],
                "_knowledge_items_to_add": Optional[List[Dict]] # <--- New: List of items to add to the KB
            }
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement the exec_async method."
        )

    async def post_async(self, shared: Dict, prep_res: Dict, exec_res: Dict):
        """
        [Refactored] Generic post-processing stage.
        - Handles knowledge base items declared in exec_res.
        - Intelligently dehydrates the payload.
        - Wraps the result in a TOOL_RESULT event.
        - Cleans up the state.
        """
        state = shared.get("state", {})
        is_error = exec_res.get("status") == "error"

        # --- START: New knowledge base handling logic ---
        knowledge_items_to_add = exec_res.get("_knowledge_items_to_add", [])
        if knowledge_items_to_add and not is_error:
            kb = shared.get('refs', {}).get('run', {}).get('runtime', {}).get("knowledge_base")
            if kb:
                logger.info("tool_kb_items_to_add", extra={"tool_name": self._tool_info['name'], "item_count": len(knowledge_items_to_add)})
                for item_data in knowledge_items_to_add:
                    # Ensure each item has the necessary metadata
                    item_data.setdefault("metadata", {})
                    item_data["metadata"]["source_tool_name"] = self._tool_info["name"]
                    item_data["metadata"]["tool_call_id"] = state.get("current_tool_call_id")
                    item_data["metadata"]["source_agent_id"] = shared.get("meta", {}).get("agent_id")
                    
                    await kb.add_item(item_data)
            else:
                logger.warning("tool_kb_not_found", extra={"tool_name": self._tool_info['name']})
        # --- END: Knowledge base handling logic ---

        # 1. Process the payload (simplified without undefined dehydrate function)
        raw_payload = exec_res.get("payload")
        
        # 2. Prepare the final payload content to be placed in the inbox
        # Ensure content is properly formatted for LLM
        content_for_llm = self._sanitize_content_for_llm(raw_payload)
        if is_error:
            # If it's an error and there's a payload, prioritize using the payload
            # Otherwise, fall back to using the error message
            if not content_for_llm:
                content_for_llm = {"error": exec_res.get("error_message", "An unknown tool error occurred.")}

        # 3. Use a helper function to add the result to the inbox
        await add_tool_result_to_inbox(
            state=state,
            tool_name=self._tool_info["name"],
            tool_call_id=state.get('current_tool_call_id'),
            is_error=is_error,
            content=content_for_llm
        )

        # 5. 触发工具完成的Flow视图更新 (使用延迟更新避免DOM冲突)
        try:
            import asyncio
            from ..events.event_triggers import trigger_view_model_update
            
            # 添加小延迟以避免与其他更新冲突
            await asyncio.sleep(0.1)
            await trigger_view_model_update(shared, "flow_view")
            logger.debug("tool_completion_flow_view_updated", extra={"tool_name": self._tool_info['name']})
        except Exception as e:
            logger.warning("tool_completion_flow_view_update_failed", extra={"tool_name": self._tool_info['name'], "error": str(e)})

        # 6. Clean up the state
        state['current_action'] = None
        
        logger.info("tool_post_processing_complete", extra={"tool_name": self._tool_info['name']})
        return "default"
    
    def _sanitize_content_for_llm(self, content: Any) -> Any:
        """
        确保传递给LLM的内容格式正确，防止"Input should be a valid string"错误
        """
        if content is None:
            return {"result": "No content available"}
        
        # 如果内容已经是字典格式，直接返回
        if isinstance(content, dict):
            # 递归检查字典中的所有值
            sanitized = {}
            for key, value in content.items():
                if isinstance(value, str):
                    # 确保字符串不为空且格式正确
                    sanitized[key] = value if value.strip() else "Empty content"
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_content_for_llm(value)
                else:
                    # 其他类型转为字符串
                    sanitized[key] = str(value) if value is not None else "None"
            return sanitized
        
        # 如果内容是列表，递归处理
        elif isinstance(content, list):
            return [self._sanitize_content_for_llm(item) for item in content]
        
        # 如果内容是字符串
        elif isinstance(content, str):
            return content if content.strip() else "Empty content"
        
        # 其他类型转为字符串
        else:
            return str(content) if content is not None else "None"

    

# Batch processing base class is disallowed - tool nodes that require batching should implement it in exec_async themselves




async def add_tool_result_to_inbox(
    state: Dict, 
    tool_name: str, 
    tool_call_id: Optional[str], 
    is_error: bool, 
    content: Any
):
    """
    A generic helper function to create a TOOL_RESULT InboxItem and add it to state['inbox'].

    Args:
        state (Dict): The agent's private state dictionary (e.g., shared['state']).
        tool_name (str): The name of the tool.
        tool_call_id (Optional[str]): The associated tool call ID.
        is_error (bool): Whether the execution resulted in an error.
        content (Any): The content to be placed in payload.content.
    """
    tool_result_payload = {
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "is_error": is_error,
        "content": content
    }

    state.setdefault('inbox', []).append({
        "item_id": f"inbox_{uuid.uuid4().hex[:8]}",
        "source": "TOOL_RESULT",
        "payload": tool_result_payload,
        "consumption_policy": "consume_on_read",
        "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}
    })
    
    logger.info("tool_result_added_to_inbox", extra={"tool_name": tool_name, "tool_call_id": tool_call_id})


# Extracted generic dehydration function
async def dehydrate_payload_recursively(data_node: Any, context: Dict, tool_info: Dict) -> Any:
    """
    Recursively traverses the payload and intelligently dehydrates oversized fields.
    This is a generic dehydration logic that can be used by different node classes.
    
    Args:
        data_node: The data node to be dehydrated.
        context: The shared context, containing the knowledge base reference.
        tool_info: Tool information, including its name, etc.
        
    Returns:
        The dehydrated data or a reference token.
    """
    kb = context.get('refs', {}).get('run', {}).get('runtime', {}).get("knowledge_base")
    if not kb:
        return data_node

    # Dehydration decision threshold (e.g., 1KB)
    DEHYDRATION_THRESHOLD_BYTES = 1024

    async def traverse(node: Any, path: str):
        if isinstance(node, dict):
            # Recursively process the dictionary, checking if each value needs to be dehydrated
            result = {}
            for key, value in node.items():
                # Check if a single key-value pair exceeds the threshold
                single_item_size = json.dumps({key: value}, ensure_ascii=False).__sizeof__()
                if single_item_size > DEHYDRATION_THRESHOLD_BYTES:
                    logger.info("tool_payload_dehydrate_dict_item", extra={"path": f"{path}.{key}", "threshold_bytes": DEHYDRATION_THRESHOLD_BYTES})
                    result[key] = await store_and_get_token(value, f"{path}.{key}")
                else:
                    # Recursively process the sub-item
                    result[key] = await traverse(value, f"{path}.{key}")
            return result
        
        elif isinstance(node, list):
            # Recursively process the list, checking if each element needs to be dehydrated
            result = []
            for i, item in enumerate(node):
                # Check if a single list item exceeds the threshold
                single_item_size = json.dumps(item, ensure_ascii=False).__sizeof__()
                if single_item_size > DEHYDRATION_THRESHOLD_BYTES:
                    logger.info("tool_payload_dehydrate_list_item", extra={"path": f"{path}[{i}]", "threshold_bytes": DEHYDRATION_THRESHOLD_BYTES})
                    result.append(await store_and_get_token(item, f"{path}[{i}]"))
                else:
                    # Recursively process the sub-item
                    result.append(await traverse(item, f"{path}[{i}]"))
            return result

        elif isinstance(node, str) and len(node.encode('utf-8')) > DEHYDRATION_THRESHOLD_BYTES:
            logger.info("tool_payload_dehydrate_string", extra={"path": path, "threshold_bytes": DEHYDRATION_THRESHOLD_BYTES})
            return await store_and_get_token(node, path)
        
        return node

    async def store_and_get_token(content_to_store: Any, original_path: str) -> str:
        metadata = {
            "item_type": "DEHYDRATED_TOOL_PAYLOAD_PART",
            "original_path": original_path,
            "source_tool_name": tool_info["name"],
            "tool_call_id": context.get("state", {}).get("current_tool_call_id")
        }
        return await kb.store_with_token(content_to_store, metadata)

    return await traverse(data_node, "payload")

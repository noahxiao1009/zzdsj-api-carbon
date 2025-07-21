"""
任务计划核心类
"""
import os
import re
import platform
from typing import List, Dict, Optional, Tuple, Any
from pathlib import PureWindowsPath, PurePosixPath
from app.utils.logging import get_logger


logger = get_logger(__name__)


# 全局文件映射
folder_files_map: Dict[str, List[str]] = {}
subfolder_files_map: Dict[str, List[str]] = {}


class Plan:
    """任务计划类"""
    
    def __init__(self, title: str = "", steps: List[str] = None, 
                 dependencies: Dict[int, List[int]] = None, work_space_path: str = ""):
        self.title = title
        self.steps = steps if steps else []
        
        # 使用步骤内容作为key存储状态、备注和详细信息
        self.step_statuses = {step: "not_started" for step in self.steps}
        self.step_notes = {step: "" for step in self.steps}
        self.step_details = {step: "" for step in self.steps}
        self.step_files = {step: "" for step in self.steps}
        
        # 使用邻接表表示依赖关系
        if dependencies:
            self.dependencies = dependencies
        else:
            # 默认依赖关系：每个步骤依赖前一个步骤
            self.dependencies = {i: [i - 1] for i in range(1, len(self.steps))} if len(self.steps) > 1 else {}
        
        self.result = ""
        self.work_space_path = work_space_path or os.environ.get("WORKSPACE_PATH", os.getcwd())
        self.plan_id = None
    
    def set_plan_result(self, plan_result: str):
        """设置计划结果"""
        self.result = plan_result
    
    def get_plan_result(self) -> str:
        """获取计划结果"""
        return self.result
    
    def get_ready_steps(self) -> List[int]:
        """获取所有前置依赖都已完成的步骤索引
        
        返回:
            List[int]: 可立即执行的步骤索引列表
        """
        logger.info(f"get_ready_steps dependencies: {self.dependencies}")
        ready_steps = []
        
        for step_index in range(len(self.steps)):
            # 获取该步骤的所有依赖
            dependencies = self.dependencies.get(step_index, [])
            
            # 检查所有依赖是否都已完成
            deps_completed = all(
                self.step_statuses.get(self.steps[int(dep)], "not_started") != "not_started" 
                for dep in dependencies
            )
            
            # 检查步骤本身是否未开始
            if deps_completed and self.step_statuses.get(self.steps[step_index]) == "not_started":
                ready_steps.append(step_index)
        
        return ready_steps
    
    def update(self, title: Optional[str] = None, steps: Optional[List[str]] = None,
               dependencies: Optional[Dict[int, List[int]]] = None) -> None:
        """更新计划，保留已完成的步骤"""
        if title:
            self.title = title
        
        if isinstance(steps, str):
            steps = steps.split("\n")
        
        if steps:
            # 保留所有现有步骤及其状态
            new_steps = []
            new_statuses = {}
            new_notes = {}
            new_details = {}
            new_files = {}
            
            # 处理所有输入步骤
            for step in steps:
                # 如果步骤存在且已开始，保留状态
                if step in self.steps and self.step_statuses.get(step) != "not_started":
                    new_steps.append(step)
                    new_statuses[step] = self.step_statuses.get(step)
                    new_notes[step] = self.step_notes.get(step, "")
                    new_details[step] = self.step_details.get(step, "")
                    new_files[step] = self.step_files.get(step, "")
                # 如果步骤存在但未开始，保留为未开始状态
                elif step in self.steps:
                    new_steps.append(step)
                    new_statuses[step] = "not_started"
                    new_notes[step] = self.step_notes.get(step, "")
                    new_details[step] = self.step_details.get(step, "")
                    new_files[step] = self.step_files.get(step, "")
                # 如果是新步骤，添加为未开始
                else:
                    new_steps.append(step)
                    new_statuses[step] = "not_started"
                    new_notes[step] = ""
                    new_details[step] = ""
                    new_files[step] = ""
            
            self.steps = new_steps
            self.step_statuses = new_statuses
            self.step_notes = new_notes
            self.step_details = new_details
            self.step_files = new_files
        
        logger.info(f"before update dependencies: {self.dependencies}")
        if dependencies:
            self.dependencies.clear()
            dependencies = {int(k): v for k, v in dependencies.items()}
            self.dependencies.update(dependencies)
        elif steps:
            # 如果没有指定依赖关系，使用默认依赖关系
            self.dependencies = {i: [i - 1] for i in range(1, len(steps))} if len(steps) > 1 else {}
        logger.info(f"after update dependencies: {self.dependencies}")
    
    def mark_step(self, step_index: int, step_status: Optional[str] = None, 
                  step_notes: Optional[str] = None, step_result: Optional[str] = None) -> None:
        """标记单个步骤的状态、备注和详情
        
        Args:
            step_index (int): 步骤索引
            step_status (Optional[str]): 新状态
            step_notes (Optional[str]): 步骤备注
            step_result (Optional[str]): 步骤结果
        """
        # 验证步骤索引
        if step_index < 0 or step_index >= len(self.steps):
            raise ValueError(f"Invalid step_index: {step_index}. Valid indices range from 0 to {len(self.steps) - 1}.")
        
        logger.info(f"step_index: {step_index}, step_status: {step_status}, step_notes: {step_notes}")
        step = self.steps[step_index]
        
        # 更新步骤状态
        if step_status is not None:
            self.step_statuses[step] = step_status
        
        # 更新步骤备注
        if step_notes is not None:
            processed_notes, file_path_info = process_text_with_workspace(step_notes, self.work_space_path)
            self.step_notes[step] = processed_notes
            self.step_files[step] = file_path_info
        
        # 更新步骤结果
        if step_result is not None:
            self.step_details[step] = step_result
        
        # 验证状态 - 如果标记为完成，检查依赖是否完成
        if step_status == "completed":
            deps = self.dependencies.get(step_index, [])
            for dep in deps:
                if dep >= len(self.steps):
                    continue
                dep_status = self.step_statuses[self.steps[int(dep)]]
                if dep_status != "completed":
                    raise ValueError(f"Cannot complete step {step_index} before its dependency {dep} is completed")
    
    def get_progress(self) -> Dict[str, int]:
        """获取计划进度统计"""
        return {
            "total": len(self.steps),
            "completed": sum(1 for status in self.step_statuses.values() if status == "completed"),
            "in_progress": sum(1 for status in self.step_statuses.values() if status == "in_progress"),
            "blocked": sum(1 for status in self.step_statuses.values() if status == "blocked"),
            "not_started": sum(1 for status in self.step_statuses.values() if status == "not_started")
        }
    
    def format(self, with_detail: bool = False) -> str:
        """格式化计划显示"""
        output = f"Plan: {self.title}\n"
        output += "=" * len(output) + "\n\n"
        
        progress = self.get_progress()
        output += f"Progress: {progress['completed']}/{progress['total']} steps completed "
        if progress['total'] > 0:
            percentage = (progress['completed'] / progress['total']) * 100
            output += f"({percentage:.1f}%)\n"
        else:
            output += "(0%)\n"
        
        output += f"Status: {progress['completed']} completed, {progress['in_progress']} in progress, "
        output += f"{progress['blocked']} blocked, {progress['not_started']} not started\n\n"
        output += "Steps:\n"
        
        for i, step in enumerate(self.steps):
            status_symbol = {
                "not_started": "[ ]",
                "in_progress": "[→]",
                "completed": "[✓]",
                "blocked": "[!]",
            }.get(self.step_statuses.get(step), "[ ]")
            
            # 显示依赖关系
            deps = self.dependencies.get(i, [])
            dep_str = f" (depends on: {', '.join(map(str, deps))})" if deps else ""
            output += f"Step{i}: {status_symbol} {step}{dep_str}\n"
            
            if self.step_notes.get(step):
                if with_detail and self.step_details.get(step):
                    output += f"   Notes: {self.step_notes.get(step)}\nDetails: {self.step_details.get(step)}\n"
                else:
                    output += f"   Notes: {self.step_notes.get(step)}\n"
        
        return output
    
    def has_blocked_steps(self) -> bool:
        """检查是否有被阻塞的步骤
        
        Returns:
            bool: 如果有任何步骤被阻塞则返回True，否则返回False
        """
        return any(status == "blocked" for status in self.step_statuses.values())
    
    def is_completed(self) -> bool:
        """检查计划是否完成"""
        if not self.steps:
            return False
        return all(status == "completed" for status in self.step_statuses.values())
    
    def is_in_progress(self) -> bool:
        """检查计划是否正在进行"""
        return any(status in ["in_progress", "completed"] for status in self.step_statuses.values())
    
    def get_completion_percentage(self) -> float:
        """获取完成百分比"""
        progress = self.get_progress()
        if progress["total"] == 0:
            return 0.0
        return (progress["completed"] / progress["total"]) * 100
    
    def get_next_steps(self) -> List[int]:
        """获取下一步可执行的步骤"""
        return self.get_ready_steps()
    
    def add_step(self, step: str, dependencies: List[int] = None) -> int:
        """添加新步骤"""
        step_index = len(self.steps)
        self.steps.append(step)
        self.step_statuses[step] = "not_started"
        self.step_notes[step] = ""
        self.step_details[step] = ""
        self.step_files[step] = ""
        
        if dependencies:
            self.dependencies[step_index] = dependencies
        
        return step_index
    
    def remove_step(self, step_index: int):
        """移除步骤"""
        if step_index < 0 or step_index >= len(self.steps):
            raise ValueError(f"Invalid step_index: {step_index}")
        
        step = self.steps[step_index]
        
        # 移除步骤
        self.steps.pop(step_index)
        
        # 移除状态信息
        self.step_statuses.pop(step, None)
        self.step_notes.pop(step, None)
        self.step_details.pop(step, None)
        self.step_files.pop(step, None)
        
        # 更新依赖关系
        new_dependencies = {}
        for idx, deps in self.dependencies.items():
            if idx > step_index:
                # 索引减1
                new_idx = idx - 1
                new_deps = [d - 1 if d > step_index else d for d in deps if d != step_index]
                new_dependencies[new_idx] = new_deps
            elif idx < step_index:
                # 移除对删除步骤的依赖
                new_deps = [d for d in deps if d != step_index]
                new_dependencies[idx] = new_deps
        
        self.dependencies = new_dependencies
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "steps": self.steps,
            "step_statuses": self.step_statuses,
            "step_notes": self.step_notes,
            "step_details": self.step_details,
            "step_files": self.step_files,
            "dependencies": self.dependencies,
            "result": self.result,
            "work_space_path": self.work_space_path,
            "plan_id": self.plan_id,
            "progress": self.get_progress(),
            "completion_percentage": self.get_completion_percentage(),
            "is_completed": self.is_completed(),
            "is_in_progress": self.is_in_progress(),
            "has_blocked_steps": self.has_blocked_steps(),
            "ready_steps": self.get_ready_steps(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plan':
        """从字典创建计划"""
        plan = cls(
            title=data.get("title", ""),
            steps=data.get("steps", []),
            dependencies=data.get("dependencies", {}),
            work_space_path=data.get("work_space_path", "")
        )
        
        plan.step_statuses = data.get("step_statuses", {})
        plan.step_notes = data.get("step_notes", {})
        plan.step_details = data.get("step_details", {})
        plan.step_files = data.get("step_files", {})
        plan.result = data.get("result", "")
        plan.plan_id = data.get("plan_id")
        
        return plan


def get_last_folder_name(workspace_path: str) -> str:
    """获取工作空间最后一级目录名"""
    workspace_path = workspace_path if workspace_path else os.environ.get("WORKSPACE_PATH")
    if not workspace_path or not os.path.exists(workspace_path):
        raise ValueError(f"{workspace_path} 工作空间路径未设置。")
    
    current_os = platform.system()
    if current_os == 'Windows':
        path_obj = PureWindowsPath(workspace_path)
    else:
        path_obj = PurePosixPath(workspace_path)
    
    return path_obj.name


def extract_and_replace_paths(text: str, folder_name: str, workspace_path: str) -> Tuple[str, List[Dict[str, str]]]:
    """提取和替换文本中的路径"""
    # 支持的文件扩展名
    valid_extensions = r"(txt|md|pdf|docx|xlsx|csv|json|xml|html|png|jpg|jpeg|svg|py)"
    
    # Linux/macOS 风格: /xxx/yyy/zzz/file.ext
    # Windows 风格: C:\xxx\yyy\file.ext
    path_file_pattern = rf'([a-zA-Z]:\\[^\s《》]+?\.{valid_extensions}|/[^\s《》]+?\.{valid_extensions})'
    
    # 中文书名号引用的文件名
    quoted_file_pattern = rf'《([^《》\s]+?\.{valid_extensions})》'
    
    result_list: List[Dict[str, str]] = []
    
    # 初始化该文件夹的文件列表
    if folder_name not in folder_files_map:
        folder_files_map[folder_name] = []
    
    def replace_path_file(match):
        full_path = match.group(1)
        filename = os.path.basename(full_path.replace("\\", "/"))
        new_path = f"{folder_name}/{filename}"
        return new_path
    
    def replace_quoted_file(match):
        filename = match.group(1)
        new_path = f"{folder_name}/{filename}"
        return new_path
    
    new_text = re.sub(path_file_pattern, replace_path_file, text)
    new_text = re.sub(quoted_file_pattern, replace_quoted_file, new_text)
    
    workspace_path = workspace_path if workspace_path else os.environ.get("WORKSPACE_PATH")
    logger.info(f"extract and replace paths work_space_path: {workspace_path}")
    
    # 读取工作空间目录下的所有文件
    if workspace_path and os.path.exists(workspace_path):
        try:
            # 遍历工作空间目录下的所有文件
            for filename in os.listdir(workspace_path):
                if os.path.isfile(os.path.join(workspace_path, filename)):
                    if filename not in folder_files_map[folder_name]:
                        folder_files_map[folder_name].append(filename)
                        result_list.append({
                            "name": filename,
                            "path": f"{folder_name}/{filename}"
                        })
            
            # 遍历工作空间目录下的所有子目录
            for root, dirs, files in os.walk(workspace_path):
                if root != workspace_path:  # 跳过根目录
                    # 获取相对路径
                    rel_path = os.path.relpath(root, workspace_path)
                    # 构建文件夹的唯一标识
                    folder_key = f"{folder_name}/{rel_path}"
                    
                    # 初始化该文件夹的文件列表
                    if folder_key not in subfolder_files_map:
                        subfolder_files_map[folder_key] = []
                    
                    for filename in files:
                        if filename not in subfolder_files_map[folder_key]:
                            subfolder_files_map[folder_key].append(filename)
                            # 构建完整的相对路径
                            full_rel_path = f"{folder_name}/{rel_path}/{filename}"
                            result_list.append({
                                "name": filename,
                                "path": full_rel_path
                            })
        except Exception as e:
            logger.error(f"Error reading workspace directory: {str(e)}", exc_info=True)
    
    return new_text, result_list


def process_text_with_workspace(text: str, work_space_path: str) -> Tuple[str, List[Dict[str, str]]]:
    """处理包含工作空间路径的文本"""
    folder_name = get_last_folder_name(work_space_path)
    return extract_and_replace_paths(text, folder_name, work_space_path)
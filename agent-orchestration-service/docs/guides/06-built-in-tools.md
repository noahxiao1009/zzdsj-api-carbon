# Built-in Tools & Web Search Configuration

The framework comes equipped with a suite of essential built-in tools that enable agents to perform a wide range of tasks, from planning and web research to file system manipulation and knowledge base queries. This guide explains the core tools and how to configure the web search provider.

## 1. Core Tool Requirements: Search & Visit

For the agent system to function effectively, especially for research tasks, it **must** have access to at least one "search" tool and one "visit" (or "fetch") tool. These are fundamental capabilities.

-   **Search Tool**: Allows the agent to query a search engine (like Google or Jina) to find relevant web pages.
-   **Visit/Fetch Tool**: Allows the agent to retrieve the content from a specific URL found during the search phase.

The framework provides two out-of-the-box implementations for these capabilities: `gemini-cli` (default) and the Jina API.

## 2. Default Provider: `gemini-cli` (The "G" Toolset)

By default, the `Associate_WebSearcher` profiles are configured to use the `G` toolset. These tools are powered by the `gemini-cli` backend, which uses Google Search for its operations.

-   **`G.google_web_search`**: The default search tool.
-   **`G.web_fetch`**: The default tool for retrieving URL content.

This configuration works out of the box without needing any API keys.

## 3. Alternative Provider: Jina API

The framework also includes built-in support for the Jina Search and Visit APIs, which can provide high-quality search results and page content.

To switch to Jina, follow these two steps:

#### Step 1: Update the Agent Profile

You need to edit the `tool_access_policy` in the relevant agent profile to use the `jina_search_and_visit` toolset instead of `G`.

For example, in `core/agent_profiles/profiles/Associate_WebSearcher_EN.yaml`:

```yaml
# core/agent_profiles/profiles/Associate_WebSearcher_EN.yaml

tool_access_policy:
  # This list will replace the list from the parent profile
  allowed_toolsets:
    # - "G" # Comment out or remove the default "G" toolset
    - "jina_search_and_visit" # Enable the Jina toolset
```

After this change, the agent will use `web_search` (the Jina implementation) instead of `G.google_web_search`.

#### Step 2: Set JINA_KEY Environment Variable

You must add your Jina API key to your `.env` file in the project's root directory.

```env
# .env file
JINA_KEY="your-jina-api-key"
```

The system will automatically pick up this key to authenticate with the Jina API.

## 4. Alternative: Custom MCP Tools

For advanced use cases, you can connect your own custom search and visit tools via the **Meta-Controller Protocol (MCP)**.

1.  **Configure Your Server**: Add your MCP-compatible tool server to `core/mcp.json`.
2.  **Enable in Profile**: Add the toolset name (which is the server name from `mcp.json`) to the agent's `allowed_toolsets` in its profile.
3.  **(Optional) Customize Prompts**: You can improve the descriptions the LLM sees for your custom tools by adding overrides in `mcp_prompt_override.yaml`.

For more details, see the [Advanced Customization](./03-advanced-customization.md) guide.

## 5. Other Key Built-in Tools

Beyond web research, the framework provides several other important tools:

#### Planning & Flow Control
-   **`manage_work_modules`**: The Principal Agent's primary tool for creating and updating the project plan.
-   **`dispatch_submodules`**: Used by the Principal to assign work modules to Associate Agents.
-   **`finish_flow`**: Signals that an agent's current task is complete, ending its execution flow.
-   **`generate_markdown_report`**: A finalization tool that provides a template for the Principal to generate its comprehensive end report.

#### Knowledge Base (RAG)

> [!NOTE]
> The RAG (Retrieval-Augmented Generation) feature is a work-in-progress and not yet a well-tested effort.

-   **`list_rag_sources`**: Discovers all available knowledge bases (both project-specific and global).
-   **`rag_query`**: Performs a semantic search on a specified internal knowledge base.

#### File System
-   **`write_file`**: Writes or overwrites content to a file in the run's dedicated workspace. This is essential for agents that generate code or web pages.
-   **`review_workspace_files`**: Lists files and directories in the workspace, and can also check HTML files for broken local links.

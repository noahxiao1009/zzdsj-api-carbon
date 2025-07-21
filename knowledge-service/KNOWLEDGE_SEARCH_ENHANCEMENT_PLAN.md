# 知识库微服务高精度检索控制开发规划

## 📋 现状分析

### 后端微服务实现程度
✅ **已完成功能**：
- 完整的知识库CRUD操作API
- 文档上传和处理流程
- 基础搜索接口(支持LlamaIndex、Agno、混合模式)
- 嵌入服务和向量化处理
- 多种文档格式支持(PDF、Word、Excel、CSV等)
- URL内容抓取功能

⚠️ **缺失功能**：
- **向量数据库索引方式选择** - 缺少HNSW、FLAT、IVF_FLAT等索引配置
- **高精度检索参数控制** - 召回率、混合检索权重比例设置不完整
- **检索方式配置** - 混合、语义、关键词检索的具体实现
- **检索测试接口** - 专门的测试和调优接口

### 前端页面实现程度
✅ **已完成功能**：
- 知识库列表展示和基础管理
- 知识库详情抽屉面板(概览、文件、搜索测试、设置四个标签页)
- 基础的搜索测试界面
- 简单的设置配置界面

⚠️ **需要完善功能**：
- **高精度检索控制面板** - 需要更专业的参数调节界面
- **索引配置界面** - 创建知识库时的索引方式选择
- **全局检索测试导航** - 独立的检索测试模块
- **检索参数调优界面** - 专业的参数配置和测试界面

## 🎯 开发目标

### 高精度知识检索控制
1. **召回率控制**：精确控制检索结果的召回率
2. **混合检索权重**：语义检索和关键词检索的权重比例
3. **检索方式选择**：混合、纯语义、纯关键词三种模式
4. **索引方式配置**：支持HNSW、FLAT、IVF_FLAT、IVF_PQ、IVF_HNSW

### 向量数据库索引优化
1. **索引类型选择**：创建知识库时可选择最优索引方式
2. **性能调优**：针对不同场景的索引参数调优
3. **索引重建**：支持动态切换索引方式

### 检索测试功能
1. **单知识库测试**：每个知识库独立的检索测试
2. **全局检索测试**：跨知识库的检索测试
3. **性能指标展示**：响应时间、准确率等指标

## 📅 开发计划

### Phase 1: 后端API增强 (2-3天)

#### 1.1 向量数据库索引配置
**文件**: `app/schemas/knowledge_schemas.py`
```python
# 添加索引类型枚举
class VectorIndexType(str, Enum):
    HNSW = "hnsw"
    FLAT = "flat" 
    IVF_FLAT = "ivf_flat"
    IVF_PQ = "ivf_pq"
    IVF_HNSW = "ivf_hnsw"

# 扩展知识库创建模型
class KnowledgeBaseCreate(BaseModel):
    # ... 现有字段 ...
    vector_index_type: VectorIndexType = Field(default=VectorIndexType.HNSW)
    index_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
```

#### 1.2 高精度检索参数
**文件**: `app/schemas/knowledge_schemas.py`
```python
# 扩展搜索请求模型
class SearchRequest(BaseModel):
    # ... 现有字段 ...
    recall_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    search_type: Literal["hybrid", "semantic", "keyword"] = Field(default="hybrid")
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    enable_re_ranking: bool = Field(default=True)
    max_candidates: int = Field(default=100, ge=10, le=500)
```

#### 1.3 新增检索测试接口
**文件**: `app/api/knowledge_routes.py`
```python
@router.post("/{kb_id}/search/test")
async def test_search_performance(
    kb_id: str,
    test_queries: List[str],
    search_configs: List[SearchRequest]
) -> Dict[str, Any]:
    """批量测试不同检索配置的性能"""
    pass

@router.get("/search/global-test")
async def global_search_test() -> Dict[str, Any]:
    """全局检索测试页面数据"""
    pass
```

### Phase 2: 前端检索控制面板 (3-4天)

#### 2.1 高精度检索控制组件
**新建文件**: `src/components/modules/knowledge-base/SearchControlPanel.tsx`

主要功能：
- 召回率滑块控制 (0.1-1.0)
- 检索方式选择 (混合/语义/关键词)
- 权重比例调节 (语义:关键词 = 70:30 可调)
- 高级参数配置 (重排序、候选数量等)
- 实时参数预览和重置功能

#### 2.2 索引配置选择器
**新建文件**: `src/components/modules/knowledge-base/IndexConfigSelector.tsx`

主要功能：
- 索引类型选择器 (HNSW/FLAT/IVF_FLAT/IVF_PQ/IVF_HNSW)
- 索引参数配置表单
- 性能对比说明
- 推荐配置建议

#### 2.3 检索测试页面
**新建文件**: `src/pages/knowledge-base/SearchTestPage.tsx`

主要功能：
- 测试查询输入区域
- 多配置并行测试
- 结果对比展示
- 性能指标图表
- 配置导出/导入

### Phase 3: 导航和集成 (1-2天)

#### 3.1 更新知识库详情抽屉
**修改文件**: `src/components/modules/knowledge-base/KnowledgeBaseDetailDrawer.tsx`

增强设置标签页：
- 集成高精度检索控制面板
- 添加索引重建功能
- 配置历史记录

#### 3.2 添加全局检索测试导航
**修改文件**: `src/routes/index.tsx`
```tsx
<Route path="/knowledge-base/search-test" element={
  <AuthGuard>
    <SearchTestPage />
  </AuthGuard>
} />
```

**修改文件**: 侧边栏导航配置
添加"检索测试"子导航项

### Phase 4: API对接和数据联调 (2天)

#### 4.1 创建API服务
**新建文件**: `src/utils/api/knowledge.ts`
```typescript
export const knowledgeAPI = {
  // 知识库管理
  createKnowledgeBase: (data: CreateKnowledgeBaseRequest) => Promise<any>,
  updateSearchConfig: (id: string, config: SearchConfig) => Promise<any>,
  
  // 检索测试
  testSearch: (id: string, params: SearchTestParams) => Promise<any>,
  globalSearchTest: (queries: string[]) => Promise<any>,
  
  // 索引管理
  rebuildIndex: (id: string, indexType: string) => Promise<any>,
  getIndexStatus: (id: string) => Promise<any>
};
```

#### 4.2 状态管理集成
**修改文件**: 相关组件
- 添加loading状态管理
- 错误处理和用户反馈
- 配置数据持久化

## 🔧 技术实现细节

### 1. 索引配置实现
```python
# 后端索引配置处理
VECTOR_INDEX_CONFIGS = {
    "hnsw": {
        "index_type": "HNSW",
        "metric_type": "COSINE", 
        "params": {"M": 16, "efConstruction": 200}
    },
    "ivf_flat": {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 100}
    },
    # ... 其他索引配置
}
```

### 2. 前端检索控制界面
```tsx
// 检索参数控制组件
const SearchControlPanel = () => {
  const [searchType, setSearchType] = useState<'hybrid' | 'semantic' | 'keyword'>('hybrid');
  const [semanticWeight, setSemanticWeight] = useState(0.7);
  const [recallThreshold, setRecallThreshold] = useState(0.8);
  
  return (
    <div className="space-y-6">
      {/* 检索方式选择 */}
      <div className="grid grid-cols-3 gap-4">
        {['hybrid', 'semantic', 'keyword'].map(type => (
          <button 
            key={type}
            className={`p-4 border rounded-lg ${searchType === type ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
            onClick={() => setSearchType(type as any)}
          >
            {type === 'hybrid' ? '混合检索' : type === 'semantic' ? '语义检索' : '关键词检索'}
          </button>
        ))}
      </div>
      
      {/* 权重控制滑块 */}
      {searchType === 'hybrid' && (
        <div className="space-y-4">
          <label className="block text-sm font-medium">语义权重: {semanticWeight}</label>
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.1"
            value={semanticWeight}
            onChange={(e) => setSemanticWeight(parseFloat(e.target.value))}
            className="w-full"
          />
        </div>
      )}
      
      {/* 召回率控制 */}
      <div className="space-y-4">
        <label className="block text-sm font-medium">召回率阈值: {recallThreshold}</label>
        <input 
          type="range" 
          min="0.1" 
          max="1" 
          step="0.05"
          value={recallThreshold}
          onChange={(e) => setRecallThreshold(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>
    </div>
  );
};
```

### 3. 检索测试功能
```tsx
// 检索测试页面
const SearchTestPage = () => {
  const [testResults, setTestResults] = useState<SearchTestResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const runSearchTest = async (query: string, configs: SearchConfig[]) => {
    setIsLoading(true);
    try {
      const results = await Promise.all(
        configs.map(config => 
          knowledgeAPI.testSearch(selectedKB, { query, ...config })
        )
      );
      setTestResults(results);
    } catch (error) {
      message.error('检索测试失败');
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="space-y-6">
      {/* 测试配置区域 */}
      <SearchTestConfigPanel onTest={runSearchTest} />
      
      {/* 结果对比展示 */}
      <SearchResultsComparison results={testResults} loading={isLoading} />
      
      {/* 性能指标图表 */}
      <PerformanceMetricsChart data={testResults} />
    </div>
  );
};
```

## 📊 验收标准

### 功能验收
- [ ] 创建知识库时可选择索引方式 (HNSW、FLAT、IVF_FLAT、IVF_PQ、IVF_HNSW)
- [ ] 检索控制面板支持召回率、权重比例、检索方式配置
- [ ] 单知识库检索测试功能完整可用
- [ ] 全局检索测试导航已添加并可访问
- [ ] 检索性能指标展示 (响应时间、召回率等)
- [ ] 配置参数可保存和重置
- [ ] 索引重建功能正常工作

### 性能验收
- [ ] 检索响应时间 < 500ms (单次查询)
- [ ] 支持并发检索测试 (最多10个配置同时测试)
- [ ] 前端参数调节响应流畅 (无明显延迟)

### 用户体验验收
- [ ] 界面设计符合现有设计规范
- [ ] 参数调节有实时预览效果
- [ ] 错误处理和用户反馈完整
- [ ] 帮助说明和推荐配置清晰

## 📝 开发进度跟踪

### Phase 1: 后端API增强
- [ ] 1.1 向量数据库索引配置 - 预计1天
- [ ] 1.2 高精度检索参数 - 预计1天  
- [ ] 1.3 新增检索测试接口 - 预计1天

### Phase 2: 前端检索控制面板
- [ ] 2.1 高精度检索控制组件 - 预计1.5天
- [ ] 2.2 索引配置选择器 - 预计1天
- [ ] 2.3 检索测试页面 - 预计1.5天

### Phase 3: 导航和集成
- [ ] 3.1 更新知识库详情抽屉 - 预计0.5天
- [ ] 3.2 添加全局检索测试导航 - 预计0.5天

### Phase 4: API对接和数据联调
- [ ] 4.1 创建API服务 - 预计1天
- [ ] 4.2 状态管理集成 - 预计1天

**总预计开发时间**: 8-10天
**当前进度**: 规划完成，准备开始Phase 1开发

## 🚀 下一步行动

1. **立即开始**: Phase 1.1 向量数据库索引配置
2. **技术准备**: 确认Milvus/PgVector索引配置参数
3. **代码审查**: 现有搜索接口的扩展点分析
4. **测试准备**: 准备不同索引类型的性能测试用例
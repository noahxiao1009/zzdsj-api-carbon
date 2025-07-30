package storage

import (
	"time"
)

// VectorRecord 向量记录
type VectorRecord struct {
	ID         string            `json:"id"`
	DocumentID string            `json:"document_id"`
	ChunkID    string            `json:"chunk_id"`
	Vector     []float32         `json:"vector"`
	Metadata   map[string]string `json:"metadata"`
	CreatedAt  time.Time         `json:"created_at"`
	UpdatedAt  time.Time         `json:"updated_at,omitempty"`
}

// CollectionInfo 集合信息
type CollectionInfo struct {
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Dimension   int               `json:"dimension"`
	MetricType  string            `json:"metric_type"`
	IndexType   string            `json:"index_type"`
	Schema      map[string]string `json:"schema"`
	CreatedAt   time.Time         `json:"created_at"`
	VectorCount int64             `json:"vector_count"`
	Status      string            `json:"status"`
}

// SearchResult 搜索结果
type SearchResult struct {
	ID       string            `json:"id"`
	Score    float32           `json:"score"`
	Vector   []float32         `json:"vector,omitempty"`
	Metadata map[string]string `json:"metadata"`
}

// RedisStats Redis统计信息
type RedisStats struct {
	Connected        bool   `json:"connected"`
	TotalConnections int    `json:"total_connections"`
	UsedMemory       string `json:"used_memory"`
	KeyspaceHits     int64  `json:"keyspace_hits"`
	KeyspaceMisses   int64  `json:"keyspace_misses"`
	TotalKeys        int64  `json:"total_keys"`
}

// MilvusStats Milvus统计信息
type MilvusStats struct {
	Connected       bool              `json:"connected"`
	Version         string            `json:"version"`
	Collections     []CollectionStats `json:"collections"`
	TotalVectors    int64             `json:"total_vectors"`
	TotalCollections int              `json:"total_collections"`
}

// CollectionStats 集合统计信息
type CollectionStats struct {
	Name        string `json:"name"`
	VectorCount int64  `json:"vector_count"`
	IndexStatus string `json:"index_status"`
	LoadStatus  string `json:"load_status"`
}

// QueryFilter 查询过滤器
type QueryFilter struct {
	DocumentIDs []string          `json:"document_ids,omitempty"`
	ChunkIDs    []string          `json:"chunk_ids,omitempty"`
	Metadata    map[string]string `json:"metadata,omitempty"`
	TimeRange   *TimeRange        `json:"time_range,omitempty"`
}

// TimeRange 时间范围
type TimeRange struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

// BatchInsertRequest 批量插入请求
type BatchInsertRequest struct {
	CollectionName string          `json:"collection_name"`
	Records        []*VectorRecord `json:"records"`
}

// BatchInsertResponse 批量插入响应
type BatchInsertResponse struct {
	VectorIDs    []string `json:"vector_ids"`
	SuccessCount int      `json:"success_count"`
	FailedCount  int      `json:"failed_count"`
}

// IndexConfig 索引配置
type IndexConfig struct {
	IndexType   string                 `json:"index_type"`
	MetricType  string                 `json:"metric_type"`
	Parameters  map[string]interface{} `json:"parameters"`
}

// CreateCollectionRequest 创建集合请求
type CreateCollectionRequest struct {
	Name        string       `json:"name"`
	Description string       `json:"description"`
	Dimension   int          `json:"dimension"`
	IndexConfig *IndexConfig `json:"index_config"`
}

// SearchRequest 搜索请求
type SearchRequest struct {
	CollectionName string       `json:"collection_name"`
	QueryVector    []float32    `json:"query_vector"`
	TopK           int          `json:"top_k"`
	Filter         *QueryFilter `json:"filter,omitempty"`
	OutputFields   []string     `json:"output_fields,omitempty"`
}

// SearchResponse 搜索响应
type SearchResponse struct {
	Results []*SearchResult `json:"results"`
	Total   int             `json:"total"`
	Time    time.Duration   `json:"time"`
}
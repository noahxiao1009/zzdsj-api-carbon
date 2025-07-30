package storage

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/milvus-io/milvus-sdk-go/v2/client"
	"github.com/milvus-io/milvus-sdk-go/v2/entity"
	log "github.com/sirupsen/logrus"

	"vector-processing-service/internal/config"
)

// MilvusClient Milvus客户端
type MilvusClient struct {
	client client.Client
	config *config.MilvusConfig
}

// NewMilvusClient 创建Milvus客户端
func NewMilvusClient(cfg *config.MilvusConfig) (*MilvusClient, error) {
	log.WithFields(log.Fields{
		"host": cfg.Host,
		"port": cfg.Port,
	}).Info("初始化Milvus客户端")

	// Milvus客户端配置
	clientConfig := client.Config{
		Address: fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
	}

	// 如果有认证信息
	if cfg.Username != "" {
		clientConfig.Username = cfg.Username
		clientConfig.Password = cfg.Password
	}

	// 创建客户端
	milvusClient, err := client.NewClient(context.Background(), clientConfig)
	if err != nil {
		return nil, fmt.Errorf("创建Milvus客户端失败: %w", err)
	}

	// 测试连接
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Connection.Timeout)
	defer cancel()

	if err := milvusClient.CheckHealth(ctx); err != nil {
		return nil, fmt.Errorf("Milvus连接测试失败: %w", err)
	}

	mc := &MilvusClient{
		client: milvusClient,
		config: cfg,
	}

	log.Info("Milvus客户端初始化成功")
	return mc, nil
}

// EnsureCollection 确保集合存在
func (m *MilvusClient) EnsureCollection(ctx context.Context, collectionName string, dimension int) error {
	// 检查集合是否存在
	hasCollection, err := m.client.HasCollection(ctx, collectionName)
	if err != nil {
		return fmt.Errorf("检查集合是否存在失败: %w", err)
	}

	if hasCollection {
		log.WithField("collection", collectionName).Debug("集合已存在")
		return nil
	}

	// 创建集合
	log.WithFields(log.Fields{
		"collection": collectionName,
		"dimension":  dimension,
	}).Info("创建新集合")

	// 定义集合Schema
	schema := &entity.Schema{
		CollectionName: collectionName,
		Description:    fmt.Sprintf("向量集合: %s", collectionName),
		Fields: []*entity.Field{
			{
				Name:       "id",
				DataType:   entity.FieldTypeVarChar,
				PrimaryKey: true,
				AutoID:     false,
				TypeParams: map[string]string{
					"max_length": "255",
				},
			},
			{
				Name:     "document_id",
				DataType: entity.FieldTypeVarChar,
				TypeParams: map[string]string{
					"max_length": "255",
				},
			},
			{
				Name:     "chunk_id",
				DataType: entity.FieldTypeVarChar,
				TypeParams: map[string]string{
					"max_length": "255",
				},
			},
			{
				Name:     "vector",
				DataType: entity.FieldTypeFloatVector,
				TypeParams: map[string]string{
					"dim": strconv.Itoa(dimension),
				},
			},
			{
				Name:     "created_at",
				DataType: entity.FieldTypeInt64,
			},
		},
	}

	// 创建集合
	if err := m.client.CreateCollection(ctx, schema, entity.DefaultShardNumber); err != nil {
		return fmt.Errorf("创建集合失败: %w", err)
	}

	// 创建索引
	if err := m.createIndex(ctx, collectionName, dimension); err != nil {
		return fmt.Errorf("创建索引失败: %w", err)
	}

	// 加载集合
	if err := m.client.LoadCollection(ctx, collectionName, false); err != nil {
		return fmt.Errorf("加载集合失败: %w", err)
	}

	log.WithField("collection", collectionName).Info("集合创建完成")
	return nil
}

// createIndex 创建索引
func (m *MilvusClient) createIndex(ctx context.Context, collectionName string, dimension int) error {
	log.WithField("collection", collectionName).Info("创建向量索引")

	// 索引参数
	indexParams := map[string]string{
		"nlist": strconv.Itoa(m.config.Default.NList),
	}

	// 创建索引
	index := entity.NewGenericIndex(
		"vector",
		m.config.Default.IndexType,
		indexParams,
	)

	return m.client.CreateIndex(ctx, collectionName, "vector", index, false)
}

// InsertVector 插入向量
func (m *MilvusClient) InsertVector(ctx context.Context, collectionName string, record *VectorRecord) (string, error) {
	log.WithFields(log.Fields{
		"collection":  collectionName,
		"document_id": record.DocumentID,
		"chunk_id":    record.ChunkID,
		"vector_dim":  len(record.Vector),
	}).Debug("插入向量")

	// 准备数据
	ids := []string{record.ID}
	documentIDs := []string{record.DocumentID}  
	chunkIDs := []string{record.ChunkID}
	vectors := [][]float32{record.Vector}
	createdAts := []int64{record.CreatedAt.Unix()}

	// 创建列数据
	idColumn := entity.NewColumnVarChar("id", ids)
	documentIDColumn := entity.NewColumnVarChar("document_id", documentIDs)
	chunkIDColumn := entity.NewColumnVarChar("chunk_id", chunkIDs)
	vectorColumn := entity.NewColumnFloatVector("vector", len(record.Vector), vectors)
	createdAtColumn := entity.NewColumnInt64("created_at", createdAts)

	// 插入数据
	_, err := m.client.Insert(
		ctx,
		collectionName,
		"",
		idColumn,
		documentIDColumn,
		chunkIDColumn,
		vectorColumn,
		createdAtColumn,
	)
	if err != nil {
		return "", fmt.Errorf("插入向量失败: %w", err)
	}

	// 刷新数据
	if err := m.client.Flush(ctx, collectionName, false); err != nil {
		log.WithError(err).WithField("collection", collectionName).Warn("刷新集合失败")
	}

	log.WithFields(log.Fields{
		"collection": collectionName,
		"vector_id":  record.ID,
	}).Debug("向量插入成功")

	return record.ID, nil
}

// BatchInsertVectors 批量插入向量
func (m *MilvusClient) BatchInsertVectors(ctx context.Context, collectionName string, records []*VectorRecord) ([]string, error) {
	if len(records) == 0 {
		return []string{}, nil
	}

	log.WithFields(log.Fields{
		"collection":  collectionName,
		"batch_size":  len(records),
		"vector_dim":  len(records[0].Vector),
	}).Info("批量插入向量")

	// 准备数据
	ids := make([]string, len(records))
	documentIDs := make([]string, len(records))
	chunkIDs := make([]string, len(records))
	vectors := make([][]float32, len(records))
	createdAts := make([]int64, len(records))

	for i, record := range records {
		ids[i] = record.ID
		documentIDs[i] = record.DocumentID
		chunkIDs[i] = record.ChunkID
		vectors[i] = record.Vector
		createdAts[i] = record.CreatedAt.Unix()
	}

	// 创建列数据
	idColumn := entity.NewColumnVarChar("id", ids)
	documentIDColumn := entity.NewColumnVarChar("document_id", documentIDs)
	chunkIDColumn := entity.NewColumnVarChar("chunk_id", chunkIDs)
	vectorColumn := entity.NewColumnFloatVector("vector", len(records[0].Vector), vectors)
	createdAtColumn := entity.NewColumnInt64("created_at", createdAts)

	// 批量插入
	_, err := m.client.Insert(
		ctx,
		collectionName,
		"",
		idColumn,
		documentIDColumn,
		chunkIDColumn,
		vectorColumn,
		createdAtColumn,
	)
	if err != nil {
		return nil, fmt.Errorf("批量插入向量失败: %w", err)
	}

	// 刷新数据
	if err := m.client.Flush(ctx, collectionName, false); err != nil {
		log.WithError(err).WithField("collection", collectionName).Warn("刷新集合失败")
	}

	log.WithFields(log.Fields{
		"collection": collectionName,
		"inserted":   len(records),
	}).Info("批量向量插入成功")

	return ids, nil
}

// SearchVectors 搜索向量
func (m *MilvusClient) SearchVectors(ctx context.Context, collectionName string, queryVector []float32, topK int) ([]*VectorRecord, error) {
	log.WithFields(log.Fields{
		"collection": collectionName,
		"vector_dim": len(queryVector),
		"top_k":      topK,
	}).Debug("搜索相似向量")

	// 搜索参数
	searchParams := entity.NewIndexFlatSearchParam()

	// 执行搜索
	results, err := m.client.Search(
		ctx,
		collectionName,
		nil,
		"",
		[]string{"id", "document_id", "chunk_id", "created_at"},
		[]entity.Vector{entity.FloatVector(queryVector)},
		"vector",
		entity.COSINE,
		topK,
		searchParams,
	)
	if err != nil {
		return nil, fmt.Errorf("搜索向量失败: %w", err)
	}

	// 解析结果
	var records []*VectorRecord
	if len(results) > 0 {
		result := results[0]
		for i := 0; i < result.ResultCount; i++ {
			// 获取字段值
			id, _ := result.Fields.GetColumn("id").Get(i)
			documentID, _ := result.Fields.GetColumn("document_id").Get(i)
			chunkID, _ := result.Fields.GetColumn("chunk_id").Get(i)
			createdAt, _ := result.Fields.GetColumn("created_at").Get(i)

			record := &VectorRecord{
				ID:         id.(string),
				DocumentID: documentID.(string),
				ChunkID:    chunkID.(string),
				// Vector: 不返回原始向量数据
				CreatedAt: time.Unix(createdAt.(int64), 0),
			}

			records = append(records, record)
		}
	}

	log.WithFields(log.Fields{
		"collection": collectionName,
		"found":      len(records),
	}).Debug("向量搜索完成")

	return records, nil
}

// GetVector 获取向量
func (m *MilvusClient) GetVector(ctx context.Context, collectionName, vectorID string) (*VectorRecord, error) {
	log.WithFields(log.Fields{
		"collection": collectionName,
		"vector_id":  vectorID,
	}).Debug("获取向量")

	// 查询向量
	expr := fmt.Sprintf("id == \"%s\"", vectorID)
	results, err := m.client.Query(
		ctx,
		collectionName,
		nil,
		expr,
		[]string{"id", "document_id", "chunk_id", "vector", "created_at"},
	)
	if err != nil {
		return nil, fmt.Errorf("查询向量失败: %w", err)
	}

	if results.Len() == 0 {
		return nil, fmt.Errorf("向量不存在: %s", vectorID)
	}

	// 解析结果
	id, _ := results.GetColumn("id").Get(0)
	documentID, _ := results.GetColumn("document_id").Get(0)
	chunkID, _ := results.GetColumn("chunk_id").Get(0)
	vectorData, _ := results.GetColumn("vector").Get(0)
	createdAt, _ := results.GetColumn("created_at").Get(0)

	record := &VectorRecord{
		ID:         id.(string),
		DocumentID: documentID.(string),
		ChunkID:    chunkID.(string),
		Vector:     vectorData.([]float32),
		CreatedAt:  time.Unix(createdAt.(int64), 0),
	}

	log.WithField("vector_id", vectorID).Debug("获取向量成功")
	return record, nil
}

// DeleteVector 删除向量
func (m *MilvusClient) DeleteVector(ctx context.Context, collectionName, vectorID string) error {
	log.WithFields(log.Fields{
		"collection": collectionName,
		"vector_id":  vectorID,
	}).Debug("删除向量")

	// 删除向量
	expr := fmt.Sprintf("id == \"%s\"", vectorID)
	if err := m.client.Delete(ctx, collectionName, "", expr); err != nil {
		return fmt.Errorf("删除向量失败: %w", err)
	}

	// 刷新数据
	if err := m.client.Flush(ctx, collectionName, false); err != nil {
		log.WithError(err).WithField("collection", collectionName).Warn("刷新集合失败")
	}

	log.WithField("vector_id", vectorID).Debug("向量删除成功")
	return nil
}

// GetCollectionInfo 获取集合信息
func (m *MilvusClient) GetCollectionInfo(ctx context.Context, collectionName string) (*CollectionInfo, error) {
	// 获取集合详情
	collection, err := m.client.DescribeCollection(ctx, collectionName)
	if err != nil {
		return nil, fmt.Errorf("获取集合详情失败: %w", err)
	}

	// 获取集合统计
	statistics, err := m.client.GetCollectionStatistics(ctx, collectionName)
	if err != nil {
		log.WithError(err).Warn("获取集合统计失败")
	}

	info := &CollectionInfo{
		Name:        collection.Schema.CollectionName,
		Description: collection.Schema.Description,
		CreatedAt:   time.Unix(collection.CreatedTime, 0),
		Schema:      make(map[string]string),
	}

	// 解析Schema
	for _, field := range collection.Schema.Fields {
		if field.Name == "vector" {
			if dim, ok := field.TypeParams["dim"]; ok {
				if dimInt, err := strconv.Atoi(dim); err == nil {
					info.Dimension = dimInt
				}
			}
		}
		info.Schema[field.Name] = field.DataType.String()
	}

	// 解析统计信息
	if statistics != nil {
		if rowCount, ok := statistics["row_count"]; ok {
			if count, err := strconv.ParseInt(rowCount, 10, 64); err == nil {
				info.VectorCount = count
			}
		}
	}

	return info, nil
}

// ListCollections 列出所有集合
func (m *MilvusClient) ListCollections(ctx context.Context) ([]string, error) {
	collections, err := m.client.ListCollections(ctx)
	if err != nil {
		return nil, fmt.Errorf("列出集合失败: %w", err)
	}

	var names []string
	for _, collection := range collections {
		names = append(names, collection.Name)
	}

	return names, nil
}

// GetStats 获取Milvus统计信息
func (m *MilvusClient) GetStats(ctx context.Context) (*MilvusStats, error) {
	stats := &MilvusStats{
		Connected: true,
	}

	// 获取版本信息
	version, err := m.client.GetVersion(ctx)
	if err != nil {
		log.WithError(err).Warn("获取Milvus版本失败")
	} else {
		stats.Version = version
	}

	// 获取集合列表
	collections, err := m.ListCollections(ctx)
	if err != nil {
		log.WithError(err).Warn("获取集合列表失败")
	} else {
		stats.TotalCollections = len(collections)
		stats.Collections = make([]CollectionStats, 0, len(collections))

		// 获取每个集合的统计信息
		for _, collectionName := range collections {
			collectionStats, err := m.client.GetCollectionStatistics(ctx, collectionName)
			if err != nil {
				log.WithError(err).WithField("collection", collectionName).Warn("获取集合统计失败")
				continue
			}

			collectionInfo := CollectionStats{
				Name: collectionName,
			}

			if rowCount, ok := collectionStats["row_count"]; ok {
				if count, err := strconv.ParseInt(rowCount, 10, 64); err == nil {
					collectionInfo.VectorCount = count
					stats.TotalVectors += count
				}
			}

			stats.Collections = append(stats.Collections, collectionInfo)
		}
	}

	return stats, nil
}

// HealthCheck 健康检查
func (m *MilvusClient) HealthCheck(ctx context.Context) error {
	return m.client.CheckHealth(ctx)
}

// Close 关闭连接
func (m *MilvusClient) Close() error {
	if m.client != nil {
		err := m.client.Close()
		if err != nil {
			log.WithError(err).Error("关闭Milvus连接失败")
			return err
		}
		log.Info("Milvus连接已关闭")
	}
	return nil
}

// CreateCollection 创建集合
func (m *MilvusClient) CreateCollection(ctx context.Context, req *CreateCollectionRequest) error {
	log.WithFields(log.Fields{
		"name":      req.Name,
		"dimension": req.Dimension,
	}).Info("创建集合")

	return m.EnsureCollection(ctx, req.Name, req.Dimension)
}

// DropCollection 删除集合
func (m *MilvusClient) DropCollection(ctx context.Context, collectionName string) error {
	log.WithField("collection", collectionName).Info("删除集合")

	return m.client.DropCollection(ctx, collectionName)
}

// LoadCollection 加载集合
func (m *MilvusClient) LoadCollection(ctx context.Context, collectionName string) error {
	log.WithField("collection", collectionName).Info("加载集合")

	return m.client.LoadCollection(ctx, collectionName, false)
}

// ReleaseCollection 释放集合
func (m *MilvusClient) ReleaseCollection(ctx context.Context, collectionName string) error {
	log.WithField("collection", collectionName).Info("释放集合")

	return m.client.ReleaseCollection(ctx, collectionName)
}
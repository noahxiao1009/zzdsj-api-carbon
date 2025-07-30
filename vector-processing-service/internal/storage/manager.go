package storage

import (
	"context"
	"fmt"
	"time"

	log "github.com/sirupsen/logrus"
)

// Manager 存储管理器
type Manager struct {
	redis  *RedisClient
	milvus *MilvusClient
}

// VectorData 向量数据
type VectorData struct {
	CollectionName string
	DocumentID     string
	ChunkID        string
	Vector         []float32
	Metadata       map[string]string
}

// NewManager 创建存储管理器
func NewManager(redis *RedisClient, milvus *MilvusClient) *Manager {
	return &Manager{
		redis:  redis,
		milvus: milvus,
	}
}

// StoreVector 存储向量
func (m *Manager) StoreVector(ctx context.Context, data *VectorData) (string, error) {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"collection":  data.CollectionName,
			"document_id": data.DocumentID,
			"chunk_id":    data.ChunkID,
			"vector_dim":  len(data.Vector),
			"duration":    time.Since(start),
		}).Debug("向量存储操作完成")
	}()

	log.WithFields(log.Fields{
		"collection":  data.CollectionName,
		"document_id": data.DocumentID,
		"chunk_id":    data.ChunkID,
		"vector_dim":  len(data.Vector),
	}).Info("开始存储向量")

	// 确保集合存在
	if err := m.milvus.EnsureCollection(ctx, data.CollectionName, len(data.Vector)); err != nil {
		return "", fmt.Errorf("确保集合存在失败: %w", err)
	}

	// 构建向量记录
	record := &VectorRecord{
		ID:         fmt.Sprintf("%s_%s", data.DocumentID, data.ChunkID),
		DocumentID: data.DocumentID,
		ChunkID:    data.ChunkID,
		Vector:     data.Vector,
		Metadata:   data.Metadata,
		CreatedAt:  time.Now(),
	}

	// 存储到Milvus
	vectorID, err := m.milvus.InsertVector(ctx, data.CollectionName, record)
	if err != nil {
		return "", fmt.Errorf("存储向量到Milvus失败: %w", err)
	}

	// 缓存到Redis（可选）
	if err := m.cacheVectorMetadata(ctx, vectorID, data); err != nil {
		log.WithError(err).WithField("vector_id", vectorID).Warn("缓存向量元数据失败")
	}

	log.WithFields(log.Fields{
		"vector_id":   vectorID,
		"collection":  data.CollectionName,
		"document_id": data.DocumentID,
		"chunk_id":    data.ChunkID,
	}).Info("向量存储成功")

	return vectorID, nil
}

// BatchStoreVectors 批量存储向量
func (m *Manager) BatchStoreVectors(ctx context.Context, vectors []*VectorData) ([]string, error) {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"batch_size": len(vectors),
			"duration":   time.Since(start),
		}).Debug("批量向量存储操作完成")
	}()

	log.WithField("batch_size", len(vectors)).Info("开始批量存储向量")

	if len(vectors) == 0 {
		return []string{}, nil
	}

	// 按集合分组
	collectionGroups := make(map[string][]*VectorData)
	for _, vector := range vectors {
		collectionGroups[vector.CollectionName] = append(collectionGroups[vector.CollectionName], vector)
	}

	var allVectorIDs []string

	// 按集合批量存储
	for collectionName, groupVectors := range collectionGroups {
		// 确保集合存在
		if len(groupVectors) > 0 {
			if err := m.milvus.EnsureCollection(ctx, collectionName, len(groupVectors[0].Vector)); err != nil {
				return nil, fmt.Errorf("确保集合 %s 存在失败: %w", collectionName, err)
			}
		}

		// 构建向量记录
		records := make([]*VectorRecord, len(groupVectors))
		for i, vector := range groupVectors {
			records[i] = &VectorRecord{
				ID:         fmt.Sprintf("%s_%s", vector.DocumentID, vector.ChunkID),
				DocumentID: vector.DocumentID,
				ChunkID:    vector.ChunkID,
				Vector:     vector.Vector,
				Metadata:   vector.Metadata,
				CreatedAt:  time.Now(),
			}
		}

		// 批量插入到Milvus
		vectorIDs, err := m.milvus.BatchInsertVectors(ctx, collectionName, records)
		if err != nil {
			return nil, fmt.Errorf("批量存储向量到集合 %s 失败: %w", collectionName, err)
		}

		allVectorIDs = append(allVectorIDs, vectorIDs...)

		// 批量缓存到Redis（可选）
		go func(ids []string, vecs []*VectorData) {
			for i, id := range ids {
				if i < len(vecs) {
					if err := m.cacheVectorMetadata(context.Background(), id, vecs[i]); err != nil {
						log.WithError(err).WithField("vector_id", id).Warn("缓存向量元数据失败")
					}
				}
			}
		}(vectorIDs, groupVectors)
	}

	log.WithFields(log.Fields{
		"batch_size":  len(vectors),
		"vector_ids":  len(allVectorIDs),
		"collections": len(collectionGroups),
	}).Info("批量向量存储成功")

	return allVectorIDs, nil
}

// SearchSimilarVectors 搜索相似向量
func (m *Manager) SearchSimilarVectors(ctx context.Context, collectionName string, queryVector []float32, topK int) ([]*VectorRecord, error) {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"collection": collectionName,
			"vector_dim": len(queryVector),
			"top_k":      topK,
			"duration":   time.Since(start),
		}).Debug("相似向量搜索操作完成")
	}()

	log.WithFields(log.Fields{
		"collection": collectionName,
		"vector_dim": len(queryVector),
		"top_k":      topK,
	}).Info("开始搜索相似向量")

	// 调用Milvus搜索
	results, err := m.milvus.SearchVectors(ctx, collectionName, queryVector, topK)
	if err != nil {
		return nil, fmt.Errorf("搜索相似向量失败: %w", err)
	}

	log.WithFields(log.Fields{
		"collection": collectionName,
		"results":    len(results),
	}).Info("相似向量搜索完成")

	return results, nil
}

// GetVector 获取向量
func (m *Manager) GetVector(ctx context.Context, collectionName, vectorID string) (*VectorRecord, error) {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"collection": collectionName,
			"vector_id":  vectorID,
			"duration":   time.Since(start),
		}).Debug("获取向量操作完成")
	}()

	// 先尝试从Redis缓存获取
	if record, err := m.getVectorFromCache(ctx, vectorID); err == nil && record != nil {
		log.WithField("vector_id", vectorID).Debug("从缓存获取向量成功")
		return record, nil
	}

	// 从Milvus获取
	record, err := m.milvus.GetVector(ctx, collectionName, vectorID)
	if err != nil {
		return nil, fmt.Errorf("从Milvus获取向量失败: %w", err)
	}

	// 异步缓存到Redis
	go func() {
		if record != nil {
			data := &VectorData{
				CollectionName: collectionName,
				DocumentID:     record.DocumentID,
				ChunkID:        record.ChunkID,
				Vector:         record.Vector,
				Metadata:       record.Metadata,
			}
			if err := m.cacheVectorMetadata(context.Background(), vectorID, data); err != nil {
				log.WithError(err).WithField("vector_id", vectorID).Warn("异步缓存向量元数据失败")
			}
		}
	}()

	log.WithField("vector_id", vectorID).Info("获取向量成功")
	return record, nil
}

// DeleteVector 删除向量
func (m *Manager) DeleteVector(ctx context.Context, collectionName, vectorID string) error {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"collection": collectionName,
			"vector_id":  vectorID,
			"duration":   time.Since(start),
		}).Debug("删除向量操作完成")
	}()

	log.WithFields(log.Fields{
		"collection": collectionName,
		"vector_id":  vectorID,
	}).Info("开始删除向量")

	// 从Milvus删除
	if err := m.milvus.DeleteVector(ctx, collectionName, vectorID); err != nil {
		return fmt.Errorf("从Milvus删除向量失败: %w", err)
	}

	// 从Redis缓存删除
	if err := m.removeVectorFromCache(ctx, vectorID); err != nil {
		log.WithError(err).WithField("vector_id", vectorID).Warn("从缓存删除向量失败")
	}

	log.WithField("vector_id", vectorID).Info("删除向量成功")
	return nil
}

// GetCollectionInfo 获取集合信息
func (m *Manager) GetCollectionInfo(ctx context.Context, collectionName string) (*CollectionInfo, error) {
	return m.milvus.GetCollectionInfo(ctx, collectionName)
}

// ListCollections 列出所有集合
func (m *Manager) ListCollections(ctx context.Context) ([]string, error) {
	return m.milvus.ListCollections(ctx)
}

// Close 关闭存储管理器
func (m *Manager) Close() error {
	var err error

	// 关闭Redis连接
	if m.redis != nil {
		if redisErr := m.redis.Close(); redisErr != nil {
			err = fmt.Errorf("关闭Redis连接失败: %w", redisErr)
			log.WithError(redisErr).Error("关闭Redis连接失败")
		}
	}

	// 关闭Milvus连接
	if m.milvus != nil {
		if milvusErr := m.milvus.Close(); milvusErr != nil {
			if err != nil {
				err = fmt.Errorf("%v; 关闭Milvus连接失败: %w", err, milvusErr)
			} else {
				err = fmt.Errorf("关闭Milvus连接失败: %w", milvusErr)
			}
			log.WithError(milvusErr).Error("关闭Milvus连接失败")
		}
	}

	if err == nil {
		log.Info("存储管理器关闭成功")
	}
	return err
}

// cacheVectorMetadata 缓存向量元数据到Redis
func (m *Manager) cacheVectorMetadata(ctx context.Context, vectorID string, data *VectorData) error {
	if m.redis == nil {
		return nil
	}

	cacheData := map[string]interface{}{
		"collection_name": data.CollectionName,
		"document_id":     data.DocumentID,
		"chunk_id":        data.ChunkID,
		"metadata":        data.Metadata,
		"cached_at":       time.Now().Unix(),
	}

	key := fmt.Sprintf("vector:meta:%s", vectorID)
	return m.redis.HMSet(ctx, key, cacheData, 24*time.Hour) // 缓存24小时
}

// getVectorFromCache 从Redis缓存获取向量元数据
func (m *Manager) getVectorFromCache(ctx context.Context, vectorID string) (*VectorRecord, error) {
	if m.redis == nil {
		return nil, fmt.Errorf("Redis客户端未初始化")
	}

	key := fmt.Sprintf("vector:meta:%s", vectorID)
	data, err := m.redis.HGetAll(ctx, key)
	if err != nil {
		return nil, err
	}

	if len(data) == 0 {
		return nil, fmt.Errorf("缓存中未找到向量元数据")
	}

	// 这里只返回元数据，不包含向量数据
	// 实际应用中可能需要完整的向量数据
	record := &VectorRecord{
		ID:         vectorID,
		DocumentID: data["document_id"],
		ChunkID:    data["chunk_id"],
		// Vector:     nil, // 缓存中不存储向量数据
		Metadata: make(map[string]string),
	}

	// 解析元数据
	if metadataStr, ok := data["metadata"]; ok {
		// 这里简化处理，实际应该反序列化JSON
		record.Metadata["cached"] = metadataStr
	}

	return record, nil
}

// removeVectorFromCache 从Redis缓存删除向量元数据
func (m *Manager) removeVectorFromCache(ctx context.Context, vectorID string) error {
	if m.redis == nil {
		return nil
	}

	key := fmt.Sprintf("vector:meta:%s", vectorID)
	return m.redis.Del(ctx, key)
}

// GetStats 获取存储统计信息
func (m *Manager) GetStats(ctx context.Context) (*StorageStats, error) {
	stats := &StorageStats{
		Timestamp: time.Now(),
	}

	// 获取Redis统计
	if m.redis != nil {
		redisStats, err := m.redis.GetStats(ctx)
		if err != nil {
			log.WithError(err).Warn("获取Redis统计失败")
		} else {
			stats.Redis = redisStats
		}
	}

	// 获取Milvus统计
	if m.milvus != nil {
		milvusStats, err := m.milvus.GetStats(ctx)
		if err != nil {
			log.WithError(err).Warn("获取Milvus统计失败")
		} else {
			stats.Milvus = milvusStats
		}
	}

	return stats, nil
}

// StorageStats 存储统计信息
type StorageStats struct {
	Timestamp time.Time       `json:"timestamp"`
	Redis     *RedisStats     `json:"redis,omitempty"`
	Milvus    *MilvusStats    `json:"milvus,omitempty"`
}

// HealthCheck 健康检查
func (m *Manager) HealthCheck(ctx context.Context) error {
	// 检查Redis连接
	if m.redis != nil {
		if err := m.redis.Ping(ctx); err != nil {
			return fmt.Errorf("Redis健康检查失败: %w", err)
		}
	}

	// 检查Milvus连接
	if m.milvus != nil {
		if err := m.milvus.HealthCheck(ctx); err != nil {
			return fmt.Errorf("Milvus健康检查失败: %w", err)
		}
	}

	return nil
}
package embedding

import (
	"context"
	"fmt"
	"strings"
	"sync"

	log "github.com/sirupsen/logrus"

	"vector-processing-service/internal/config"
)

// Service 嵌入服务
type Service struct {
	config    *config.EmbeddingConfig
	providers map[string]Provider
	mutex     sync.RWMutex
}

// Provider 嵌入提供者接口
type Provider interface {
	GenerateEmbedding(ctx context.Context, text string) ([]float32, error)
	GetDimension() int
	GetMaxBatchSize() int
	GetMaxInputLength() int
	GetName() string
}

// NewService 创建嵌入服务
func NewService(cfg *config.EmbeddingConfig) (*Service, error) {
	log.Info("初始化嵌入服务")

	service := &Service{
		config:    cfg,
		providers: make(map[string]Provider),
	}

	// 初始化提供者
	if err := service.initProviders(); err != nil {
		return nil, fmt.Errorf("初始化嵌入提供者失败: %w", err)
	}

	log.WithField("providers", len(service.providers)).Info("嵌入服务初始化完成")
	return service, nil
}

// initProviders 初始化提供者
func (s *Service) initProviders() error {
	for modelName, modelConfig := range s.config.Models {
		provider, err := s.createProvider(modelName, &modelConfig)
		if err != nil {
			log.WithError(err).WithField("model", modelName).Error("创建嵌入提供者失败")
			continue
		}

		s.providers[modelName] = provider
		log.WithField("model", modelName).Info("嵌入提供者创建成功")
	}

	if len(s.providers) == 0 {
		return fmt.Errorf("没有可用的嵌入提供者")
	}

	return nil
}

// createProvider 创建提供者
func (s *Service) createProvider(modelName string, config *config.EmbeddingModel) (Provider, error) {
	switch strings.ToLower(config.Provider) {
	case "openai":
		return NewOpenAIProvider(modelName, config)
	case "siliconflow":
		return NewSiliconFlowProvider(modelName, config)
	case "huggingface":
		return NewHuggingFaceProvider(modelName, config)
	default:
		return nil, fmt.Errorf("不支持的嵌入提供者: %s", config.Provider)
	}
}

// GenerateEmbedding 生成嵌入向量
func (s *Service) GenerateEmbedding(ctx context.Context, text string, modelName string) ([]float32, error) {
	if modelName == "" {
		modelName = s.config.DefaultModel
	}

	s.mutex.RLock()
	provider, exists := s.providers[modelName]
	s.mutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("模型不存在: %s", modelName)
	}

	// 检查输入长度
	if len(text) > provider.GetMaxInputLength() {
		return nil, fmt.Errorf("输入文本长度超过限制: %d > %d", len(text), provider.GetMaxInputLength())
	}

	// 生成嵌入向量
	embedding, err := provider.GenerateEmbedding(ctx, text)
	if err != nil {
		return nil, fmt.Errorf("生成嵌入向量失败: %w", err)
	}

	log.WithFields(log.Fields{
		"model":     modelName,
		"text_len":  len(text),
		"dimension": len(embedding),
	}).Debug("嵌入向量生成成功")

	return embedding, nil
}

// BatchGenerateEmbeddings 批量生成嵌入向量
func (s *Service) BatchGenerateEmbeddings(ctx context.Context, texts []string, modelName string) ([][]float32, error) {
	if modelName == "" {
		modelName = s.config.DefaultModel
	}

	s.mutex.RLock()
	provider, exists := s.providers[modelName]
	s.mutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("模型不存在: %s", modelName)
	}

	// 检查批次大小
	if len(texts) > provider.GetMaxBatchSize() {
		return nil, fmt.Errorf("批次大小超过限制: %d > %d", len(texts), provider.GetMaxBatchSize())
	}

	// 批量生成嵌入向量
	embeddings := make([][]float32, len(texts))
	var wg sync.WaitGroup
	var mutex sync.Mutex
	var firstError error

	for i, text := range texts {
		wg.Add(1)
		go func(index int, inputText string) {
			defer wg.Done()

			embedding, err := provider.GenerateEmbedding(ctx, inputText)
			if err != nil {
				mutex.Lock()
				if firstError == nil {
					firstError = err
				}
				mutex.Unlock()
				return
			}

			mutex.Lock()
			embeddings[index] = embedding
			mutex.Unlock()
		}(i, text)
	}

	wg.Wait()

	if firstError != nil {
		return nil, fmt.Errorf("批量生成嵌入向量失败: %w", firstError)
	}

	log.WithFields(log.Fields{
		"model":      modelName,
		"batch_size": len(texts),
		"dimension":  len(embeddings[0]),
	}).Debug("批量嵌入向量生成成功")

	return embeddings, nil
}

// GetModelInfo 获取模型信息
func (s *Service) GetModelInfo(modelName string) (*ModelInfo, error) {
	if modelName == "" {
		modelName = s.config.DefaultModel
	}

	s.mutex.RLock()
	provider, exists := s.providers[modelName]
	s.mutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("模型不存在: %s", modelName)
	}

	return &ModelInfo{
		Name:           modelName,
		Provider:       provider.GetName(),
		Dimension:      provider.GetDimension(),
		MaxBatchSize:   provider.GetMaxBatchSize(),
		MaxInputLength: provider.GetMaxInputLength(),
	}, nil
}

// ListModels 列出所有模型
func (s *Service) ListModels() []*ModelInfo {
	s.mutex.RLock()
	defer s.mutex.RUnlock()

	var models []*ModelInfo
	for modelName, provider := range s.providers {
		models = append(models, &ModelInfo{
			Name:           modelName,
			Provider:       provider.GetName(),
			Dimension:      provider.GetDimension(),
			MaxBatchSize:   provider.GetMaxBatchSize(),
			MaxInputLength: provider.GetMaxInputLength(),
		})
	}

	return models
}

// GetDefaultModel 获取默认模型
func (s *Service) GetDefaultModel() string {
	return s.config.DefaultModel
}

// ModelInfo 模型信息
type ModelInfo struct {
	Name           string `json:"name"`
	Provider       string `json:"provider"`
	Dimension      int    `json:"dimension"`
	MaxBatchSize   int    `json:"max_batch_size"`
	MaxInputLength int    `json:"max_input_length"`
}
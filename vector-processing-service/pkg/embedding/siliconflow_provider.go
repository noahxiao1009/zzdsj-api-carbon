package embedding

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	log "github.com/sirupsen/logrus"

	"vector-processing-service/internal/config"
)

// SiliconFlowProvider SiliconFlow嵌入提供者
type SiliconFlowProvider struct {
	modelName  string
	config     *config.EmbeddingModel
	httpClient *http.Client
	apiKey     string
	apiBase    string
}

// SiliconFlowRequest 请求结构
type SiliconFlowRequest struct {
	Model string   `json:"model"`
	Input []string `json:"input"`
}

// SiliconFlowResponse 响应结构
type SiliconFlowResponse struct {
	Object string                 `json:"object"`
	Data   []SiliconFlowEmbedding `json:"data"`
	Model  string                 `json:"model"`
	Usage  SiliconFlowUsage       `json:"usage"`
}

// SiliconFlowEmbedding 嵌入数据
type SiliconFlowEmbedding struct {
	Object    string    `json:"object"`
	Index     int       `json:"index"`
	Embedding []float32 `json:"embedding"`
}

// SiliconFlowUsage 使用情况
type SiliconFlowUsage struct {
	PromptTokens int `json:"prompt_tokens"`
	TotalTokens  int `json:"total_tokens"`
}

// NewSiliconFlowProvider 创建SiliconFlow提供者
func NewSiliconFlowProvider(modelName string, config *config.EmbeddingModel) (*SiliconFlowProvider, error) {
	// 从环境变量获取API密钥
	apiKey := os.Getenv("SILICONFLOW_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("SILICONFLOW_API_KEY环境变量未设置")
	}

	apiBase := config.APIBase
	if apiBase == "" {
		apiBase = "https://api.siliconflow.cn/v1"
	}

	provider := &SiliconFlowProvider{
		modelName: modelName,
		config:    config,
		apiKey:    apiKey,
		apiBase:   apiBase,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}

	log.WithFields(log.Fields{
		"model":     modelName,
		"provider":  "siliconflow",
		"api_base":  apiBase,
		"dimension": config.Dimension,
	}).Info("SiliconFlow嵌入提供者创建成功")

	return provider, nil
}

// GenerateEmbedding 生成嵌入向量
func (p *SiliconFlowProvider) GenerateEmbedding(ctx context.Context, text string) ([]float32, error) {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"provider": "siliconflow",
			"model":    p.modelName,
			"duration": time.Since(start),
		}).Debug("SiliconFlow嵌入生成完成")
	}()

	// 构建请求
	request := SiliconFlowRequest{
		Model: p.modelName,
		Input: []string{text},
	}

	// 序列化请求
	requestBody, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("序列化请求失败: %w", err)
	}

	// 创建HTTP请求
	url := fmt.Sprintf("%s/embeddings", p.apiBase)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, fmt.Errorf("创建HTTP请求失败: %w", err)
	}

	// 设置请求头
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", p.apiKey))

	// 发送请求
	resp, err := p.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("发送HTTP请求失败: %w", err)
	}
	defer resp.Body.Close()

	// 读取响应
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}

	// 检查状态码
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API请求失败，状态码: %d, 响应: %s", resp.StatusCode, string(responseBody))
	}

	// 解析响应
	var response SiliconFlowResponse
	if err := json.Unmarshal(responseBody, &response); err != nil {
		return nil, fmt.Errorf("解析响应失败: %w", err)
	}

	// 检查响应数据
	if len(response.Data) == 0 {
		return nil, fmt.Errorf("响应数据为空")
	}

	embedding := response.Data[0].Embedding
	if len(embedding) == 0 {
		return nil, fmt.Errorf("嵌入向量为空")
	}

	log.WithFields(log.Fields{
		"provider":      "siliconflow",
		"model":         p.modelName,
		"dimension":     len(embedding),
		"prompt_tokens": response.Usage.PromptTokens,
		"total_tokens":  response.Usage.TotalTokens,
		"duration":      time.Since(start),
	}).Debug("SiliconFlow嵌入向量生成成功")

	return embedding, nil
}

// GetDimension 获取向量维度
func (p *SiliconFlowProvider) GetDimension() int {
	return p.config.Dimension
}

// GetMaxBatchSize 获取最大批次大小
func (p *SiliconFlowProvider) GetMaxBatchSize() int {
	return p.config.MaxBatchSize
}

// GetMaxInputLength 获取最大输入长度
func (p *SiliconFlowProvider) GetMaxInputLength() int {
	return p.config.MaxInputLength
}

// GetName 获取提供者名称
func (p *SiliconFlowProvider) GetName() string {
	return "siliconflow"
}

// BatchGenerateEmbeddings 批量生成嵌入向量
func (p *SiliconFlowProvider) BatchGenerateEmbeddings(ctx context.Context, texts []string) ([][]float32, error) {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"provider":   "siliconflow",
			"model":      p.modelName,
			"batch_size": len(texts),
			"duration":   time.Since(start),
		}).Debug("SiliconFlow批量嵌入生成完成")
	}()

	// 检查批次大小
	if len(texts) > p.config.MaxBatchSize {
		return nil, fmt.Errorf("批次大小超过限制: %d > %d", len(texts), p.config.MaxBatchSize)
	}

	// 构建请求
	request := SiliconFlowRequest{
		Model: p.modelName,
		Input: texts,
	}

	// 序列化请求
	requestBody, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("序列化请求失败: %w", err)
	}

	// 创建HTTP请求
	url := fmt.Sprintf("%s/embeddings", p.apiBase)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, fmt.Errorf("创建HTTP请求失败: %w", err)
	}

	// 设置请求头
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", p.apiKey))

	// 发送请求
	resp, err := p.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("发送HTTP请求失败: %w", err)
	}
	defer resp.Body.Close()

	// 读取响应
	responseBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}

	// 检查状态码
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API请求失败，状态码: %d, 响应: %s", resp.StatusCode, string(responseBody))
	}

	// 解析响应
	var response SiliconFlowResponse
	if err := json.Unmarshal(responseBody, &response); err != nil {
		return nil, fmt.Errorf("解析响应失败: %w", err)
	}

	// 检查响应数据
	if len(response.Data) != len(texts) {
		return nil, fmt.Errorf("响应数据长度不匹配: %d vs %d", len(response.Data), len(texts))
	}

	// 提取嵌入向量
	embeddings := make([][]float32, len(texts))
	for i, data := range response.Data {
		if data.Index >= len(embeddings) {
			return nil, fmt.Errorf("响应数据索引超出范围: %d >= %d", data.Index, len(embeddings))
		}
		embeddings[data.Index] = data.Embedding
	}

	log.WithFields(log.Fields{
		"provider":      "siliconflow",
		"model":         p.modelName,
		"batch_size":    len(texts),
		"dimension":     len(embeddings[0]),
		"prompt_tokens": response.Usage.PromptTokens,
		"total_tokens":  response.Usage.TotalTokens,
		"duration":      time.Since(start),
	}).Debug("SiliconFlow批量嵌入向量生成成功")

	return embeddings, nil
}

// HealthCheck 健康检查
func (p *SiliconFlowProvider) HealthCheck(ctx context.Context) error {
	// 使用一个简单的文本进行测试
	_, err := p.GenerateEmbedding(ctx, "health check")
	if err != nil {
		return fmt.Errorf("SiliconFlow提供者健康检查失败: %w", err)
	}
	return nil
}
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

// OpenAIProvider OpenAI嵌入提供者
type OpenAIProvider struct {
	modelName  string
	config     *config.EmbeddingModel
	httpClient *http.Client
	apiKey     string
	apiBase    string
}

// OpenAIRequest OpenAI请求结构
type OpenAIRequest struct {
	Model string   `json:"model"`
	Input []string `json:"input"`
}

// OpenAIResponse OpenAI响应结构
type OpenAIResponse struct {
	Object string           `json:"object"`
	Data   []OpenAIEmbedding `json:"data"`
	Model  string           `json:"model"`
	Usage  OpenAIUsage      `json:"usage"`
}

// OpenAIEmbedding OpenAI嵌入数据
type OpenAIEmbedding struct {
	Object    string    `json:"object"`
	Index     int       `json:"index"`
	Embedding []float32 `json:"embedding"`
}

// OpenAIUsage OpenAI使用情况
type OpenAIUsage struct {
	PromptTokens int `json:"prompt_tokens"`
	TotalTokens  int `json:"total_tokens"`
}

// NewOpenAIProvider 创建OpenAI提供者
func NewOpenAIProvider(modelName string, config *config.EmbeddingModel) (*OpenAIProvider, error) {
	// 从环境变量获取API密钥
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("OPENAI_API_KEY环境变量未设置")
	}

	apiBase := config.APIBase
	if apiBase == "" {
		apiBase = "https://api.openai.com/v1"
	}

	provider := &OpenAIProvider{
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
		"provider":  "openai",
		"api_base":  apiBase,
		"dimension": config.Dimension,
	}).Info("OpenAI嵌入提供者创建成功")

	return provider, nil
}

// GenerateEmbedding 生成嵌入向量
func (p *OpenAIProvider) GenerateEmbedding(ctx context.Context, text string) ([]float32, error) {
	start := time.Now()
	defer func() {
		log.WithFields(log.Fields{
			"provider": "openai",
			"model":    p.modelName,
			"duration": time.Since(start),
		}).Debug("OpenAI嵌入生成完成")
	}()

	// 构建请求
	request := OpenAIRequest{
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
	var response OpenAIResponse
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
		"provider":      "openai",
		"model":         p.modelName,
		"dimension":     len(embedding),
		"prompt_tokens": response.Usage.PromptTokens,
		"total_tokens":  response.Usage.TotalTokens,
		"duration":      time.Since(start),
	}).Debug("OpenAI嵌入向量生成成功")

	return embedding, nil
}

// GetDimension 获取向量维度
func (p *OpenAIProvider) GetDimension() int {
	return p.config.Dimension
}

// GetMaxBatchSize 获取最大批次大小
func (p *OpenAIProvider) GetMaxBatchSize() int {
	return p.config.MaxBatchSize
}

// GetMaxInputLength 获取最大输入长度
func (p *OpenAIProvider) GetMaxInputLength() int {
	return p.config.MaxInputLength
}

// GetName 获取提供者名称
func (p *OpenAIProvider) GetName() string {
	return "openai"
}

// HealthCheck 健康检查
func (p *OpenAIProvider) HealthCheck(ctx context.Context) error {
	// 使用一个简单的文本进行测试
	_, err := p.GenerateEmbedding(ctx, "health check")
	if err != nil {
		return fmt.Errorf("OpenAI提供者健康检查失败: %w", err)
	}
	return nil
}
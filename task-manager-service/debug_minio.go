package main

import (
	"context"
	"fmt"
	"log"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

func main() {
	// 使用与配置文件相同的参数
	endpoint := "localhost:9000"
	accessKey := "zzdsjadmin"
	secretKey := "zzdsjadmin"
	bucketName := "knowledge-files"
	useSSL := false

	// 初始化MinIO客户端
	minioClient, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(accessKey, secretKey, ""),
		Secure: useSSL,
	})
	if err != nil {
		log.Fatalf("Failed to initialize MinIO client: %v", err)
	}

	fmt.Println("MinIO客户端初始化成功")

	// 测试桶存在性检查
	ctx := context.Background()
	exists, err := minioClient.BucketExists(ctx, bucketName)
	if err != nil {
		log.Fatalf("Failed to check bucket existence: %v", err)
	}

	if exists {
		fmt.Printf("✓ 桶 '%s' 存在\n", bucketName)
	} else {
		fmt.Printf("⚠️  桶 '%s' 不存在\n", bucketName)
	}

	// 列出所有桶
	buckets, err := minioClient.ListBuckets(ctx)
	if err != nil {
		log.Fatalf("Failed to list buckets: %v", err)
	}

	fmt.Println("所有可用的桶:")
	for _, bucket := range buckets {
		fmt.Printf("  - %s (创建时间: %s)\n", bucket.Name, bucket.CreationDate)
	}

	fmt.Println("MinIO连接测试成功完成!")
}
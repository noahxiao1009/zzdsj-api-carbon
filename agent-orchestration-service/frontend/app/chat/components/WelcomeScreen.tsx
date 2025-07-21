import React from 'react';
import { observer } from 'mobx-react-lite';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { selectionStore } from '@/app/stores/selectionStore';
import { Sparkles, Zap } from 'lucide-react';

interface WelcomeScreenProps {
  currentInput: string;
  onInputChange: (value: string) => void;
  onSendMessage: () => void;
  onKeyPress: (e: React.KeyboardEvent) => void;
  isLoading: boolean;
}

export const WelcomeScreen = observer(function WelcomeScreen({ currentInput, onInputChange, onSendMessage, onKeyPress, isLoading }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Main Content - 移除顶部栏，直接全屏显示 */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-8">
        {/* Hero Section */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center mb-6">
            {/* NextBuilder Z Logo 设计 */}
            <div style={{
              width: '64px',
              height: '64px',
              background: 'linear-gradient(135deg, #00c9ff 0%, #92fe9d 100%)',
              borderRadius: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              boxShadow: '0 8px 25px rgba(0, 201, 255, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2)',
              overflow: 'hidden'
            }}>
              {/* Z字母设计 */}
              <div style={{
                fontSize: '32px',
                fontWeight: '800',
                color: '#ffffff',
                fontFamily: 'Arial Black, sans-serif',
                textShadow: '0 2px 4px rgba(0, 0, 0, 0.3)',
                transform: 'perspective(100px) rotateX(10deg)',
                position: 'relative',
                zIndex: 2
              }}>
                Z
              </div>
              
              {/* 背景装饰效果 */}
              <div style={{
                position: 'absolute',
                top: '-50%',
                left: '-50%',
                width: '200%',
                height: '200%',
                background: 'radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%)',
                transform: 'rotate(45deg)',
                zIndex: 1
              }} />
            </div>
          </div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent mb-4">
            NextBuilder AI 助手
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl">
            我可以帮助您构建项目、分析代码、解决问题。请告诉我您的需求。
          </p>
        </div>

        {/* Input Card */}
        <div className="w-full max-w-4xl mb-8">
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-xl border border-gray-200/50 p-6">
            <div className="relative">
              <Textarea
                value={currentInput}
                onChange={(e) => onInputChange(e.target.value)}
                onKeyPress={onKeyPress}
                placeholder="描述您的项目需求或提出技术问题..."
                className="min-h-[120px] resize-none w-full border-0 bg-transparent text-base placeholder:text-gray-400 focus-visible:ring-0 focus-visible:ring-offset-0"
              />
              <Button 
                onClick={onSendMessage}
                disabled={!currentInput.trim() || isLoading}
                className="absolute right-3 bottom-3 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white px-6 py-2 rounded-lg shadow-lg transition-all duration-200 transform hover:scale-105"
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    生成中...
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4" />
                    开始对话
                  </div>
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
          <div className="bg-white/60 backdrop-blur-sm rounded-xl p-6 border border-gray-200/50 hover:bg-white/80 transition-all duration-200 hover:shadow-lg">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-blue-100 p-2 rounded-lg">
                <Sparkles className="w-5 h-5 text-blue-600" />
              </div>
              <h3 className="font-semibold text-gray-800">智能分析</h3>
            </div>
            <p className="text-sm text-gray-600">深度分析代码结构，提供优化建议和最佳实践</p>
          </div>
          
          <div className="bg-white/60 backdrop-blur-sm rounded-xl p-6 border border-gray-200/50 hover:bg-white/80 transition-all duration-200 hover:shadow-lg">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-green-100 p-2 rounded-lg">
                <Zap className="w-5 h-5 text-green-600" />
              </div>
              <h3 className="font-semibold text-gray-800">快速构建</h3>
            </div>
            <p className="text-sm text-gray-600">基于需求快速生成代码模板和项目结构</p>
          </div>
          
          <div className="bg-white/60 backdrop-blur-sm rounded-xl p-6 border border-gray-200/50 hover:bg-white/80 transition-all duration-200 hover:shadow-lg">
            <div className="flex items-center gap-3 mb-3">
              <div className="bg-purple-100 p-2 rounded-lg">
                <Sparkles className="w-5 h-5 text-purple-600" />
              </div>
              <h3 className="font-semibold text-gray-800">创新方案</h3>
            </div>
            <p className="text-sm text-gray-600">提供创新的解决方案和技术选型建议</p>
          </div>
        </div>
      </div>
    </div>
  );
});

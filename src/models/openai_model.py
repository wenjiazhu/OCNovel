from openai import OpenAI
import numpy as np
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential
from .base_model import BaseModel
import logging
import json
import time
import os

# 导入网络管理相关模块
try:
    from ..network.config import PoolConfig
    from ..network.model_client import ModelHTTPClient, ModelClientFactory
    from ..network.errors import NetworkError, TimeoutError, ConnectionError
    NETWORK_AVAILABLE = True
except ImportError:
    NETWORK_AVAILABLE = False
    # 使用标准HTTP客户端

class OpenAIModel(BaseModel):
    """OpenAI模型实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        
        # 检查是否为火山引擎配置
        if config.get("type") == "volcengine":
            self.is_volcengine = True
            self.thinking_enabled = config.get("thinking_enabled", True)
            self._init_volcengine_client(config)
        else:
            self.is_volcengine = False
            self.thinking_enabled = False
            self._init_standard_client(config)
            
    def _init_volcengine_client(self, config: Dict[str, Any]):
        """初始化火山引擎客户端"""
        timeout = config.get("timeout", 300)
        base_url = config.get("base_url")
        
        # 备用API配置
        self.fallback_enabled = config.get("fallback_enabled", False)
        if self.fallback_enabled:
            self.fallback_base_url = config.get("fallback_base_url", "https://api.siliconflow.cn/v1")
            self.fallback_api_key = config.get("fallback_api_key", "")
            self.fallback_model_name = config.get("fallback_model_name", "deepseek-ai/DeepSeek-R1")
        
        # 初始化火山引擎客户端
        self.volcengine_client = OpenAI(
            api_key=config["api_key"],
            base_url=base_url,
            timeout=timeout
        )
        
        logging.info(f"火山引擎DeepSeek-V3.1模型初始化完成: {base_url}, 深度思考: {self.thinking_enabled}")
        
    def _init_standard_client(self, config: Dict[str, Any]):
        """初始化标准OpenAI客户端（原有逻辑）"""
        # 增加超时时间，特别是对于本地服务器
        timeout = config.get("timeout", 120)  # 默认120秒
        base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
        
        # 备用API配置
        self.fallback_base_url = "https://api.siliconflow.cn/v1"
        self.fallback_api_key = os.getenv("OPENAI_EMBEDDING_API_KEY", "")  # 使用embedding的API key作为备用
        # 根据当前模型类型选择备用模型
        if "gemini-2.5-flash" in self.model_name:
            self.fallback_model_name = "moonshotai/Kimi-K2-Instruct"  # 使用Kimi-K2作为gemini-2.5-flash的备用
        elif "gemini-2.5-pro" in self.model_name:
            self.fallback_model_name = "Qwen/Qwen3-235B-A22B-Thinking-2507"  # 使用Qwen作为gemini-2.5-pro的备用
        else:
            self.fallback_model_name = "deepseek-ai/DeepSeek-R1"  # 默认备用模型
        
        # 初始化网络管理客户端（如果可用）
        if NETWORK_AVAILABLE:
            # 创建连接池配置
            pool_config = PoolConfig(
                max_connections=config.get("max_connections", 100),
                max_connections_per_host=config.get("max_connections_per_host", 10),
                connection_timeout=config.get("connection_timeout", 30.0),
                read_timeout=config.get("read_timeout", timeout),
                idle_timeout=config.get("idle_timeout", 300.0),
                enable_http2=config.get("enable_http2", True),
                enable_keepalive=config.get("enable_keepalive", True)
            )
            
            # 创建网络管理客户端
            self.network_client = ModelClientFactory.create_openai_client(
                base_url=base_url,
                api_key=config["api_key"],
                pool_config=pool_config,
                timeout=timeout
            )
            
            # 创建备用客户端
            if self.fallback_api_key:
                self.fallback_network_client = ModelClientFactory.create_openai_client(
                    base_url=self.fallback_base_url,
                    api_key=self.fallback_api_key,
                    pool_config=pool_config,
                    timeout=180  # 备用API使用更长的超时时间
                )
            else:
                self.fallback_network_client = None
            
            logging.info(f"OpenAI model initialized with network management: {base_url}, timeout: {timeout}s")
        else:
            # 回退到原始OpenAI客户端
            self.network_client = None
            self.fallback_network_client = None
            
        # 保持原始客户端作为备用
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=base_url,
            timeout=timeout
        )
        logging.info(f"OpenAI model initialized with base URL: {base_url}, timeout: {timeout}s")
        
    def _build_volcengine_messages(self, prompt: str) -> list:
        """构建火山引擎消息格式"""
        messages = [{"role": "user", "content": prompt}]
        
        if self.thinking_enabled:
            # 添加深度思考指令
            thinking_instruction = """
请使用深度思考模式来回答这个问题。在回答之前，请在<thinking>标签中详细分析问题，
考虑多个角度和可能的解决方案，然后给出最终的回答。
"""
            messages[0]["content"] = thinking_instruction + "\n\n" + prompt
        
        return messages
    
    def _process_thinking_output(self, content: str) -> str:
        """处理包含思考过程的输出"""
        # 提取思考过程和最终答案
        if "<thinking>" in content and "</thinking>" in content:
            # 记录思考过程用于调试
            thinking_start = content.find("<thinking>")
            thinking_end = content.find("</thinking>") + len("</thinking>")
            thinking_process = content[thinking_start:thinking_end]
            
            logging.debug(f"深度思考过程: {thinking_process[:500]}...")
            
            # 返回思考标签后的内容作为最终答案
            final_answer = content[thinking_end:].strip()
            if final_answer:
                return final_answer
            else:
                # 如果没有思考标签后的内容，返回整个内容
                return content
        
        return content
    
    def _create_fallback_client(self):
        """创建备用客户端"""
        if self.fallback_api_key:
            logging.warning(f"切换到备用API: {self.fallback_base_url}, 模型: {self.fallback_model_name}")
            return OpenAI(
                api_key=self.fallback_api_key,
                base_url=self.fallback_base_url,
                timeout=180  # 备用API使用更长的超时时间
            )
        return None
    
    def _generate_with_volcengine(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """使用火山引擎DeepSeek-V3.1生成文本"""
        logging.info(f"使用火山引擎DeepSeek-V3.1生成文本，提示词长度: {len(prompt)}")
        
        # 构建消息
        messages = self._build_volcengine_messages(prompt)
        
        # 火山引擎 DeepSeek-V3.1 的 max_tokens 限制为 32768
        effective_max_tokens = max_tokens or self.config.get("max_tokens", 8192)
        if effective_max_tokens > 32768:
            logging.warning(f"max_tokens {effective_max_tokens} 超过火山引擎限制，调整为 32768")
            effective_max_tokens = 32768
        
        # 设置生成参数
        generation_params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.config.get("temperature", 0.7),
            "max_tokens": effective_max_tokens
        }
        
        try:
            response = self.volcengine_client.chat.completions.create(**generation_params)
            content = response.choices[0].message.content
            
            if content is None:
                raise Exception("火山引擎模型返回空内容")
            
            # 处理深度思考输出
            if self.thinking_enabled:
                content = self._process_thinking_output(content)
            
            logging.info(f"火山引擎生成成功，返回内容长度: {len(content)}")
            return content
            
        except Exception as e:
            logging.error(f"火山引擎生成失败: {str(e)}")
            
            # 尝试使用备用模型
            if self.fallback_enabled and self.fallback_api_key:
                return self._generate_with_fallback(prompt, max_tokens)
            
            raise e
    
    def _generate_with_fallback(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """使用备用模型生成文本"""
        logging.warning(f"切换到备用模型: {self.fallback_model_name}")
        
        fallback_client = OpenAI(
            api_key=self.fallback_api_key,
            base_url=self.fallback_base_url,
            timeout=180
        )
        
        try:
            response = fallback_client.chat.completions.create(
                model=self.fallback_model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or 8192,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise Exception("备用模型返回空内容")
                
            logging.info(f"备用模型生成成功，返回内容长度: {len(content)}")
            return content
            
        except Exception as fallback_error:
            logging.error(f"备用模型也失败了: {str(fallback_error)}")
            raise fallback_error
    
    def _use_network_client_for_generation(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """使用网络管理客户端进行文本生成"""
        try:
            # 如果提示词太长，进行截断
            max_prompt_length = 65536  # 设置最大提示词长度
            if len(prompt) > max_prompt_length:
                logging.warning(f"提示词过长 ({len(prompt)} 字符)，截断到 {max_prompt_length} 字符")
                prompt = prompt[:max_prompt_length]
            
            messages = [{"role": "user", "content": prompt}]
            
            # 使用网络管理客户端
            response_data = self.network_client.chat_completion(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            content = response_data.get('choices', [{}])[0].get('message', {}).get('content')
            if content is None:
                raise Exception("模型返回空内容")
                
            logging.info(f"网络管理客户端生成成功，返回内容长度: {len(content)}")
            return content
            
        except (NetworkError, TimeoutError, ConnectionError) as e:
            logging.error(f"网络管理客户端生成失败: {str(e)}")
            
            # 如果配置了备用网络客户端，尝试使用
            if self.fallback_network_client:
                logging.warning("尝试使用备用网络客户端...")
                try:
                    response_data = self.fallback_network_client.chat_completion(
                        model=self.fallback_model_name,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=0.7
                    )
                    
                    content = response_data.get('choices', [{}])[0].get('message', {}).get('content')
                    if content is None:
                        raise Exception("备用模型返回空内容")
                        
                    logging.info(f"备用网络客户端生成成功，返回内容长度: {len(content)}")
                    return content
                    
                except Exception as fallback_error:
                    logging.error(f"备用网络客户端也失败了: {str(fallback_error)}")
            
            # 重新抛出原始异常
            raise e
        except Exception as e:
            logging.error(f"网络管理客户端生成出现未知错误: {str(e)}")
            raise e
    
    def _use_network_client_for_embedding(self, text: str) -> np.ndarray:
        """使用网络管理客户端获取嵌入向量"""
        try:
            logging.info(f"使用网络管理客户端生成嵌入向量，文本长度: {len(text)}")
            
            response_data = self.network_client.embeddings(
                model=self.model_name,
                input_text=text
            )
            
            # 解析响应
            if 'data' in response_data and len(response_data['data']) > 0:
                embedding = np.array(response_data['data'][0]['embedding'])
                logging.info(f"网络管理客户端成功生成嵌入向量，维度: {len(embedding)}")
                return embedding
            else:
                logging.error("嵌入响应数据为空或无效")
                raise Exception("嵌入响应数据为空或无效")
                
        except (NetworkError, TimeoutError, ConnectionError) as e:
            logging.error(f"网络管理客户端嵌入失败: {str(e)}")
            raise e
        except Exception as e:
            logging.error(f"网络管理客户端嵌入出现未知错误: {str(e)}")
            raise e
        
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本"""
        logging.info(f"开始生成文本，模型: {self.model_name}, 提示词长度: {len(prompt)}")
        
        # 如果是火山引擎，使用专用的生成方法
        if self.is_volcengine:
            return self._generate_with_volcengine(prompt, max_tokens)
        
        # 优先使用网络管理客户端
        if NETWORK_AVAILABLE and self.network_client:
            try:
                return self._use_network_client_for_generation(prompt, max_tokens)
            except Exception as e:
                logging.warning(f"网络管理客户端失败，回退到原始客户端: {str(e)}")
        
        # 回退到原始实现
        try:
            # 如果提示词太长，进行截断
            max_prompt_length = 65536  # 设置最大提示词长度
            if len(prompt) > max_prompt_length:
                logging.warning(f"提示词过长 ({len(prompt)} 字符)，截断到 {max_prompt_length} 字符")
                prompt = prompt[:max_prompt_length]
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise Exception("模型返回空内容")
                
            logging.info(f"文本生成成功，返回内容长度: {len(content)}")
            return content
            
        except Exception as e:
            logging.error(f"OpenAI generation error: {str(e)}")
            
            # 如果是连接错误且配置了备用API，尝试使用备用API
            if ("timeout" in str(e).lower() or "connection" in str(e).lower()) and self.fallback_api_key:
                logging.warning("检测到连接错误，尝试使用备用API...")
                fallback_client = self._create_fallback_client()
                if fallback_client:
                    try:
                        response = fallback_client.chat.completions.create(
                            model=self.fallback_model_name,  # 使用备用模型名称
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=max_tokens,
                            temperature=0.7
                        )
                        content = response.choices[0].message.content
                        if content is None:
                            raise Exception("备用模型返回空内容")
                            
                        logging.info(f"使用备用API生成成功，返回内容长度: {len(content)}")
                        return content
                    except Exception as fallback_error:
                        logging.error(f"备用API也失败了: {str(fallback_error)}")
            
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                logging.warning("检测到超时或连接错误，将重试...")
                time.sleep(5)  # 等待5秒后重试
            raise Exception(f"OpenAI generation error: {str(e)}")
            
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        logging.info(f"生成嵌入向量，文本长度: {len(text)}")
        logging.info(f"使用模型: {self.model_name}")
        
        # 优先使用网络管理客户端
        if NETWORK_AVAILABLE and self.network_client:
            try:
                return self._use_network_client_for_embedding(text)
            except Exception as e:
                logging.warning(f"网络管理客户端嵌入失败，回退到原始客户端: {str(e)}")
        
        # 回退到原始实现
        try:
            # 打印请求信息
            request_data = {
                "model": self.model_name,
                "input": text[:100] + "..." if len(text) > 100 else text  # 只打印前100个字符
            }
            logging.info(f"Request data: {json.dumps(request_data, ensure_ascii=False)}")
            
            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=text
                )
                
                # 打印响应信息
                if hasattr(response, 'data') and len(response.data) > 0:
                    embedding = np.array(response.data[0].embedding)
                    logging.info(f"Successfully generated embedding with dimension {len(embedding)}")
                    return embedding
                else:
                    logging.error("Response data is empty or invalid")
                    logging.error(f"Response: {response}")
                    raise Exception("Embedding response is empty or invalid")
                    
            except Exception as api_error:
                logging.error(f"API call failed: {str(api_error)}")
                # 检查是否有response属性（OpenAI API错误通常有）
                if hasattr(api_error, 'response') and api_error.response is not None:
                    logging.error(f"Response status: {api_error.response.status_code}")
                    logging.error(f"Response body: {api_error.response.text}")
                raise
                
        except Exception as e:
            logging.error(f"OpenAI embedding error: {str(e)}")
            raise
    
    def close(self):
        """关闭模型客户端"""
        if NETWORK_AVAILABLE:
            if self.network_client:
                self.network_client.close()
            if self.fallback_network_client:
                self.fallback_network_client.close()
        logging.debug("OpenAI model clients closed")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            self.close()
        except:
            pass 
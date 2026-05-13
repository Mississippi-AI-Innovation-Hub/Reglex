import { useState, useEffect, useRef, useCallback } from 'react';
import { ChatService } from '../services/api';
import type { Message, ResearchFilters } from '../types';

const STORAGE_KEY = 'chat_history_v4';

export function useChat(apiEndpoint: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const chatService = useRef<ChatService | null>(null);

  // Initialize service and load history
  useEffect(() => {
    chatService.current = new ChatService(apiEndpoint);
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved).map((m: Record<string, unknown>) => ({
          ...m,
          timestamp: new Date(m.timestamp as string),
        }));
        setMessages(parsed);
      } catch {
        // ignore corrupt data
      }
    }
  }, [apiEndpoint]);

  // Persist messages
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  }, [messages]);

  const sendMessage = useCallback(async (
    content: string,
    options?: {
      filters?: ResearchFilters;
      mode?: 'research' | 'chat' | 'compare' | 'count';
      model?: string;
    }
  ) => {
    if (!content.trim() || isLoading || !chatService.current) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // Build conversation history for multi-turn context
      const history = messages
        .filter(m => !m.isError)
        .map(m => ({ role: m.role, content: m.content }));

      const response = await chatService.current.sendMessage(content, {
        filters: options?.filters,
        mode: options?.mode,
        model: options?.model,
        history,
      });

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        timestamp: new Date(),
        intent: response.intent,
        metadata: response.metadata,
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (err) {
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: err instanceof Error ? err.message : 'Unknown error',
        isError: true,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, messages]);

  const clearChat = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { messages, isLoading, sendMessage, clearChat };
}

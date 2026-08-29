import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { ChatMessage, SharedMemory } from '../types';
import { Send, Bot, User as UserIcon, Sparkles, RefreshCw, Users, Brain } from 'lucide-react';
import { format } from 'date-fns';

interface ChatPanelProps {
  onEventChange: () => void;
  sharedCalendarId?: number | null;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ onEventChange, sharedCalendarId = null }) => {
  const { accessToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [memories, setMemories] = useState<SharedMemory[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Load chat history and memories when switching calendar scope
  useEffect(() => {
    if (!accessToken) return;
    setInitialLoading(true);

    if (sharedCalendarId) {
      // Scoped Shared Chat
      Promise.all([
        api.getSharedChatHistory(accessToken, sharedCalendarId),
        api.listSharedMemories(accessToken, sharedCalendarId),
      ])
        .then(([history, mems]) => {
          setMessages(history);
          setMemories(mems);
        })
        .catch((err) => console.error('Failed to load shared chat:', err))
        .finally(() => setInitialLoading(false));
    } else {
      // Personal Chat
      setMemories([]);
      api
        .getChatHistory(accessToken)
        .then(setMessages)
        .catch((err) => console.error('Failed to load personal chat:', err))
        .finally(() => setInitialLoading(false));
    }
  }, [accessToken, sharedCalendarId]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || input;
    if (!text.trim() || !accessToken || loading) return;

    const userMessageContent = text.trim();
    setInput('');

    // Optimistically add user message
    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userMessageContent,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setLoading(true);

    try {
      let response;
      if (sharedCalendarId) {
        response = await api.sendSharedChat(accessToken, sharedCalendarId, userMessageContent);
        // Refresh shared memories if a group memory was created
        api.listSharedMemories(accessToken, sharedCalendarId).then(setMemories).catch(() => {});
      } else {
        response = await api.sendChat(accessToken, userMessageContent);
      }

      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.reply,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (response.action_taken) {
        onEventChange();
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Error: ${err.message || 'Failed to communicate with AI Assistant.'}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-slate-800/80 border-b border-slate-700/80 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className={`p-1.5 rounded-lg ${sharedCalendarId ? 'bg-indigo-600/30 text-indigo-400' : 'bg-blue-600/30 text-blue-400'}`}>
            {sharedCalendarId ? <Users className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">
              {sharedCalendarId ? 'Shared Group AI Copilot' : 'Personal AI Copilot'}
            </h2>
            <p className="text-[10px] text-slate-400">
              {sharedCalendarId ? 'Group-scoped memory & scheduling' : 'Natural language schedule manager'}
            </p>
          </div>
        </div>
      </div>

      {/* Shared Memories Banner (if in group calendar) */}
      {sharedCalendarId && memories.length > 0 && (
        <div className="bg-indigo-950/40 border-b border-indigo-900/40 px-3 py-2 text-xs text-indigo-300">
          <div className="flex items-center space-x-1.5 font-medium mb-1 text-[11px] text-indigo-400">
            <Brain className="w-3 h-3" />
            <span>Group Context & Memories:</span>
          </div>
          <div className="space-y-0.5">
            {memories.map((m) => (
              <div key={m.id} className="text-[11px] text-slate-300 truncate">
                • {m.content}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && !initialLoading && (
          <div className="text-center py-8 px-4 text-slate-400">
            <Sparkles className="w-8 h-8 mx-auto text-blue-400/60 mb-2" />
            <p className="text-xs font-medium text-slate-300">
              {sharedCalendarId ? 'Start collaborating in this shared calendar!' : 'How can I assist your schedule today?'}
            </p>
            <p className="text-[11px] text-slate-500 mt-1">
              {sharedCalendarId
                ? 'Try: "Remember that this group meets Tuesdays, avoid scheduling then"'
                : 'Try: "Schedule sync with Alex on Monday at 10am"'}
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start space-x-2.5 ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
          >
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] shrink-0 ${
                msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-indigo-600 text-white'
              }`}
            >
              {msg.role === 'user' ? <UserIcon className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
            </div>
            <div
              className={`max-w-[82%] rounded-2xl px-3.5 py-2 text-xs leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-sm shadow-md'
                  : 'bg-slate-800 text-slate-200 border border-slate-700/60 rounded-tl-sm shadow-sm'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 bg-slate-900/90 border-t border-slate-800">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              sharedCalendarId
                ? 'Message group copilot or add a team rule...'
                : 'Ask AI copilot to manage schedule...'
            }
            className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="p-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl transition"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
};

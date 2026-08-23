import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { ChatMessage } from '../types';
import { Send, Bot, User as UserIcon, Sparkles, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';

interface ChatPanelProps {
  onEventChange: () => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ onEventChange }) => {
  const { accessToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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

  useEffect(() => {
    if (!accessToken) return;
    api
      .getChatHistory(accessToken)
      .then((history) => {
        setMessages(history);
      })
      .catch((err) => {
        console.error('Failed to load chat history:', err);
      })
      .finally(() => {
        setInitialLoading(false);
      });
  }, [accessToken]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || input;
    if (!text.trim() || !accessToken || loading) return;

    const userMessageContent = text.trim();
    setInput('');

    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userMessageContent,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setLoading(true);

    try {
      const response = await api.sendChat(accessToken, userMessageContent);

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

  const samplePrompts = [
    'Make sure I buy groceries on Thursday',
    'Dr. Smith consultation at 3pm on Friday for 45 minutes',
    'CS50 final project submission deadline is this Sunday at 23:59',
    'What is on my schedule for tomorrow?',
  ];

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[580px] lg:h-[700px] backdrop-blur">
      <div className="px-5 py-4 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 text-white shadow-md shadow-indigo-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-white text-sm flex items-center gap-1.5">
              Gemini AI Copilot
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Live DB
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">Semantic event scheduling, deadlines & agenda summaries</p>
          </div>
        </div>
      </div>

      <div className="flex-1 p-4 overflow-y-auto space-y-3.5 scrollbar-thin">
        {initialLoading ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-500">
            <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mr-2" />
            Loading conversation...
          </div>
        ) : messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-4 py-8">
            <Bot className="w-10 h-10 text-indigo-400 mb-3 opacity-80" />
            <h4 className="text-sm font-semibold text-white mb-1">How can I help you today?</h4>
            <p className="text-xs text-slate-400 mb-4 max-w-xs leading-relaxed">
              Tell me about reminders, meetings, appointments, deadlines, or ask about your schedule.
            </p>
            <div className="space-y-1.5 w-full max-w-xs">
              {samplePrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSendMessage(prompt)}
                  className="w-full text-left text-[11px] p-2 rounded-xl bg-slate-800/60 hover:bg-indigo-950/60 border border-slate-700/50 hover:border-indigo-500/40 text-slate-300 hover:text-indigo-200 transition truncate"
                >
                  "{prompt}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'bg-slate-800/90 border border-slate-700/60 text-slate-200 shadow-sm whitespace-pre-wrap'
                }`}
              >
                {msg.content}
                <div
                  className={`text-[9px] mt-1 text-right font-mono ${
                    msg.role === 'user' ? 'text-indigo-200' : 'text-slate-500'
                  }`}
                >
                  {format(new Date(msg.created_at), 'h:mm a')}
                </div>
              </div>

              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-400 shrink-0 mt-0.5">
                  <UserIcon className="w-4 h-4" />
                </div>
              )}
            </div>
          ))
        )}

        {loading && (
          <div className="flex gap-2.5 justify-start">
            <div className="w-7 h-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
              <Bot className="w-4 h-4" />
            </div>
            <div className="rounded-2xl px-3.5 py-2.5 bg-slate-800/90 border border-slate-700/60 text-xs text-slate-400 flex items-center gap-1.5">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" />
              <span>Analyzing intent & checking calendar...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-3 border-t border-slate-800 bg-slate-950/60">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder="e.g. Dr. Smith consultation at 3pm on Friday for 45 minutes..."
            className="flex-1 px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed shadow-md shadow-indigo-600/25 transition"
            title="Send Message"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};

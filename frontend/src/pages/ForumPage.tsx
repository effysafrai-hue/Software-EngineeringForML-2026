import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  Send,
  Image as ImageIcon,
  Video,
  EyeOff,
  User,
  Trash2,
  Search,
  Plus,
  ArrowLeft,
  Paperclip,
  CheckCircle,
  AlertCircle,
  X,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Post, Comment, PostDetail } from '../types';

export const ForumFeed: React.FC<{ onSelectPost: (id: number) => void }> = ({ onSelectPost }) => {
  const { accessToken } = useAuth();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showComposer, setShowComposer] = useState(false);

  const fetchPosts = async () => {
    if (!accessToken) return;
    try {
      setLoading(true);
      const data = await api.getPosts(accessToken, search);
      setPosts(data);
    } catch (err) {
      console.error('Failed to fetch posts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts();
  }, [accessToken, search]);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/80 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <MessageSquare className="text-indigo-400 w-6 h-6" />
            Campus Community Forum
          </h1>
          <p className="text-slate-400 text-xs mt-1">
            Discuss coursework, share updates, or ask questions anonymously.
          </p>
        </div>
        <button
          onClick={() => setShowComposer(true)}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-500/20 transition active:scale-95"
        >
          <Plus className="w-4 h-4" />
          Create Post
        </button>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 w-4 h-4" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search discussions, topics, or questions..."
          className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
        />
      </div>

      {/* Composer Modal */}
      {showComposer && (
        <PostComposer
          onClose={() => setShowComposer(false)}
          onPostCreated={() => {
            setShowComposer(false);
            fetchPosts();
          }}
        />
      )}

      {/* Posts List */}
      {loading ? (
        <div className="text-center py-16">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-500 border-t-transparent"></div>
          <p className="text-slate-400 mt-2 text-xs">Loading discussions...</p>
        </div>
      ) : posts.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/40 rounded-2xl border border-dashed border-slate-800">
          <MessageSquare className="w-10 h-10 text-slate-600 mx-auto mb-2" />
          <p className="text-slate-300 text-sm font-medium">No discussions found</p>
          <p className="text-slate-500 text-xs mt-1">Be the first to start a conversation!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {posts.map((post) => (
            <div
              key={post.id}
              onClick={() => onSelectPost(post.id)}
              className="group bg-slate-900/70 hover:bg-slate-900 border border-slate-800 hover:border-indigo-500/50 rounded-2xl p-5 transition cursor-pointer shadow-md hover:shadow-indigo-500/10"
            >
              <div className="flex items-center justify-between gap-2 mb-2.5">
                <div className="flex items-center gap-2">
                  {post.anonymous ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-slate-800 text-slate-300 rounded-full text-[11px] font-medium border border-slate-700">
                      <EyeOff className="w-3 h-3 text-slate-400" />
                      Anonymous
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-indigo-500/10 text-indigo-300 rounded-full text-[11px] font-medium border border-indigo-500/30">
                      <User className="w-3 h-3 text-indigo-400" />
                      {post.author_email || 'Student'}
                    </span>
                  )}
                  <span className="text-[11px] text-slate-500">
                    {new Date(post.created_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-[11px] text-slate-400 bg-slate-800 px-2 py-0.5 rounded-lg">
                  <MessageSquare className="w-3 h-3 text-slate-400" />
                  <span>{post.comment_count}</span>
                </div>
              </div>

              <h2 className="text-base font-bold text-white group-hover:text-indigo-300 transition-colors">
                {post.title}
              </h2>
              <p className="text-slate-300 text-xs mt-1.5 line-clamp-2 leading-relaxed">
                {post.body}
              </p>

              {/* Media Thumbnails */}
              {post.media_urls && post.media_urls.length > 0 && (
                <div className="flex items-center gap-2 mt-3 overflow-x-auto pb-1">
                  {post.media_urls.map((url, idx) => (
                    <div
                      key={idx}
                      className="relative w-16 h-16 rounded-lg overflow-hidden bg-slate-950 border border-slate-800 flex-shrink-0"
                    >
                      {url.endsWith('.mp4') || url.endsWith('.webm') || url.endsWith('.mov') ? (
                        <div className="w-full h-full flex items-center justify-center bg-slate-950 text-indigo-400">
                          <Video className="w-5 h-5" />
                        </div>
                      ) : (
                        <img
                          src={url}
                          alt="thumbnail"
                          className="w-full h-full object-cover"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const PostComposer: React.FC<{
  onClose: () => void;
  onPostCreated: () => void;
}> = ({ onClose, onPostCreated }) => {
  const { accessToken } = useAuth();
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [anonymous, setAnonymous] = useState(false);
  const [mediaUrls, setMediaUrls] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !accessToken) return;

    setError(null);
    setUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const res = await api.uploadMedia(accessToken, file);
        setMediaUrls((prev) => [...prev, res.url]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to upload media. Check file size/type.');
    } finally {
      setUploading(false);
    }
  };

  const removeMedia = (idx: number) => {
    setMediaUrls((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !body.trim() || !accessToken) {
      setError('Title and content are required.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await api.createPost(accessToken, {
        title: title.trim(),
        body: body.trim(),
        media_urls: mediaUrls,
        anonymous,
      });
      onPostCreated();
    } catch (err: any) {
      setError(err?.message || 'Failed to publish post.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-slate-800">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Plus className="w-4 h-4 text-indigo-400" />
            Create Forum Discussion
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Tips for preparing for CS229 final exam?"
              className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Content
            </label>
            <textarea
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Share details, questions, or resources..."
              className="w-full px-3.5 py-2 bg-slate-800 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              required
            />
          </div>

          {/* Media Previews */}
          {mediaUrls.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {mediaUrls.map((url, idx) => (
                <div
                  key={idx}
                  className="relative group w-20 h-20 rounded-xl overflow-hidden bg-slate-950 border border-slate-800"
                >
                  {url.endsWith('.mp4') || url.endsWith('.webm') || url.endsWith('.mov') ? (
                    <div className="w-full h-full flex items-center justify-center bg-slate-950 text-indigo-400">
                      <Video className="w-6 h-6" />
                    </div>
                  ) : (
                    <img src={url} alt="upload" className="w-full h-full object-cover" />
                  )}
                  <button
                    type="button"
                    onClick={() => removeMedia(idx)}
                    className="absolute top-1 right-1 p-1 bg-red-600 text-white rounded-full opacity-0 group-hover:opacity-100 transition"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-slate-800">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={anonymous}
                  onChange={(e) => setAnonymous(e.target.checked)}
                  className="w-3.5 h-3.5 rounded text-indigo-600 bg-slate-800 border-slate-700 focus:ring-indigo-500"
                />
                <span className="text-xs font-medium text-slate-300 flex items-center gap-1">
                  <EyeOff className="w-3.5 h-3.5 text-purple-400" />
                  Post Anonymously
                </span>
              </label>

              <label className="cursor-pointer inline-flex items-center gap-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg border border-slate-700 transition">
                <Paperclip className="w-3.5 h-3.5" />
                <span>Attach</span>
                <input
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/webm,video/quicktime"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 text-slate-400 hover:text-white text-xs"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || uploading}
                className="px-4 py-1.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg transition"
              >
                {submitting ? 'Publishing...' : 'Publish'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export const PostDetailPage: React.FC<{
  postId: number;
  onBack: () => void;
}> = ({ postId, onBack }) => {
  const { accessToken } = useAuth();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [commentBody, setCommentBody] = useState('');
  const [commentAnon, setCommentAnon] = useState(false);
  const [commentMedia, setCommentMedia] = useState<string[]>([]);
  const [submittingComment, setSubmittingComment] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = async () => {
    if (!accessToken) return;
    try {
      setLoading(true);
      const data = await api.getPostDetail(accessToken, postId);
      setPost(data);
    } catch (err) {
      console.error('Failed to load post detail', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [accessToken, postId]);

  const handleCommentUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !accessToken) return;
    try {
      for (let i = 0; i < files.length; i++) {
        const res = await api.uploadMedia(accessToken, files[i]);
        setCommentMedia((prev) => [...prev, res.url]);
      }
    } catch (err: any) {
      setError('Media upload failed.');
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentBody.trim() || !accessToken) return;

    setSubmittingComment(true);
    setError(null);
    try {
      await api.addComment(accessToken, postId, {
        body: commentBody.trim(),
        media_urls: commentMedia,
        anonymous: commentAnon,
      });
      setCommentBody('');
      setCommentMedia([]);
      setCommentAnon(false);
      fetchDetail();
    } catch (err: any) {
      setError(err?.message || 'Failed to submit comment.');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleDeletePost = async () => {
    if (!window.confirm('Are you sure you want to delete this discussion?') || !accessToken) return;
    try {
      await api.deletePost(accessToken, postId);
      onBack();
    } catch (err: any) {
      alert(err?.message || 'Cannot delete post.');
    }
  };

  if (loading) {
    return (
      <div className="text-center py-20">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-500 border-t-transparent"></div>
        <p className="text-slate-400 mt-2 text-xs">Loading discussion...</p>
      </div>
    );
  }

  if (!post) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-300 text-sm">Post not found.</p>
        <button
          onClick={onBack}
          className="mt-3 px-3 py-1.5 bg-indigo-600 text-white rounded-xl text-xs"
        >
          Return to Forum
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-slate-400 hover:text-white text-xs font-medium transition"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to Discussions
      </button>

      <div className="bg-slate-900/80 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {post.anonymous ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-slate-800 text-slate-300 rounded-full text-[11px] font-medium border border-slate-700">
                <EyeOff className="w-3 h-3 text-slate-400" />
                Anonymous
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-indigo-500/10 text-indigo-300 rounded-full text-[11px] font-medium border border-indigo-500/30">
                <User className="w-3 h-3 text-indigo-400" />
                {post.author_email || 'Student'}
              </span>
            )}
            <span className="text-[11px] text-slate-500">
              {new Date(post.created_at).toLocaleString()}
            </span>
          </div>

          <button
            onClick={handleDeletePost}
            className="text-slate-500 hover:text-red-400 p-1.5 rounded-lg transition"
            title="Delete post"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        <h1 className="text-xl font-bold text-white">{post.title}</h1>
        <p className="text-slate-200 text-xs leading-relaxed whitespace-pre-wrap">{post.body}</p>

        {post.media_urls && post.media_urls.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3 border-t border-slate-800">
            {post.media_urls.map((url, idx) => (
              <div key={idx} className="rounded-xl overflow-hidden bg-slate-950 border border-slate-800">
                {url.endsWith('.mp4') || url.endsWith('.webm') || url.endsWith('.mov') ? (
                  <video controls className="w-full h-56 object-cover">
                    <source src={url} />
                  </video>
                ) : (
                  <a href={url} target="_blank" rel="noreferrer">
                    <img src={url} alt="attachment" className="w-full h-56 object-cover hover:scale-105 transition duration-200" />
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Replies */}
      <div className="bg-slate-900/60 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-indigo-400" />
          Replies ({post.comments.length})
        </h3>

        <div className="space-y-3">
          {post.comments.length === 0 ? (
            <p className="text-slate-500 text-xs italic">No replies yet.</p>
          ) : (
            post.comments.map((c) => (
              <div key={c.id} className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {c.anonymous ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-800 text-slate-300 rounded-full text-[10px] border border-slate-700">
                        <EyeOff className="w-2.5 h-2.5 text-slate-400" />
                        Anonymous
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-500/10 text-indigo-300 rounded-full text-[10px] border border-indigo-500/30">
                        <User className="w-2.5 h-2.5 text-indigo-400" />
                        {c.author_email || 'Student'}
                      </span>
                    )}
                    <span className="text-[10px] text-slate-500">
                      {new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
                <p className="text-slate-200 text-xs whitespace-pre-wrap">{c.body}</p>
                {c.media_urls && c.media_urls.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {c.media_urls.map((url, idx) => (
                      <div key={idx} className="w-16 h-16 rounded-lg overflow-hidden bg-slate-950 border border-slate-800">
                        <img src={url} alt="media" className="w-full h-full object-cover" />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Comment form */}
        <form onSubmit={handleAddComment} className="pt-4 border-t border-slate-800 space-y-3">
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <textarea
            rows={2}
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            placeholder="Write a reply..."
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            required
          />

          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 cursor-pointer text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={commentAnon}
                  onChange={(e) => setCommentAnon(e.target.checked)}
                  className="w-3.5 h-3.5 rounded text-indigo-600 bg-slate-800 border-slate-700"
                />
                <span className="flex items-center gap-1 text-[11px]">
                  <EyeOff className="w-3 h-3 text-purple-400" />
                  Reply Anonymously
                </span>
              </label>

              <label className="cursor-pointer inline-flex items-center gap-1 px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg border border-slate-700 transition">
                <Paperclip className="w-3 h-3" />
                <span className="text-[11px]">Attach</span>
                <input
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/webm,video/quicktime"
                  onChange={handleCommentUpload}
                  className="hidden"
                />
              </label>
            </div>

            <button
              type="submit"
              disabled={submittingComment}
              className="inline-flex items-center gap-1 px-4 py-1.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow transition"
            >
              <Send className="w-3 h-3" />
              <span>{submittingComment ? 'Sending...' : 'Reply'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export const ForumPage: React.FC = () => {
  const [selectedPostId, setSelectedPostId] = useState<number | null>(null);

  if (selectedPostId !== null) {
    return (
      <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-5">
        <PostDetailPage postId={selectedPostId} onBack={() => setSelectedPostId(null)} />
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-5">
      <ForumFeed onSelectPost={(id) => setSelectedPostId(id)} />
    </div>
  );
};

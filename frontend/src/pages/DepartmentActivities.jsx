import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  Download,
  FileText,
  Image,
  MessageSquareText,
  Paperclip,
  Send,
  Trash2,
} from 'lucide-react';
import api, { getApiErrorMessage } from '../services/api';
import { useAuth } from '../context/AuthContext';
import ProfileAvatar from '../components/ProfileAvatar';

const categories = ['Announcement', 'Event', 'Opportunity', 'Workshop', 'General'];
const staffRoles = ['super_admin', 'hod', 'faculty'];
const initialForm = { title: '', content: '', category: 'General' };

const formatDate = (value) => new Date(value).toLocaleString(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export default function DepartmentActivities() {
  const { user } = useAuth();
  const [posts, setPosts] = useState([]);
  const [category, setCategory] = useState('');
  const [form, setForm] = useState(initialForm);
  const [attachment, setAttachment] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [commentDrafts, setCommentDrafts] = useState({});
  const [postingCommentId, setPostingCommentId] = useState(null);

  const loadPosts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('/activities/', {
        params: { limit: 100, ...(category ? { category } : {}) },
      });
      setPosts(response.data);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
      setPosts([]);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    let active = true;
    api.get('/activities/', {
      params: { limit: 100, ...(category ? { category } : {}) },
    })
      .then((response) => {
        if (active) setPosts(response.data);
      })
      .catch((requestError) => {
        if (active) {
          setError(getApiErrorMessage(requestError));
          setPosts([]);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [category]);

  const submitPost = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const data = new FormData();
      data.append('title', form.title);
      data.append('content', form.content);
      data.append('category', form.category);
      if (attachment) data.append('attachment', attachment);

      await api.post('/activities/', data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setForm(initialForm);
      setAttachment(null);
      setFileInputKey((key) => key + 1);
      setNotice('Your post has been shared with the department.');
      await loadPosts();
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setSaving(false);
    }
  };

  const downloadAttachment = async (post) => {
    setError('');
    try {
      const response = await api.get(`/activities/${post.id}/attachment`, {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = post.attachment_filename || 'activity-attachment';
      link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    }
  };

  const deletePost = async (post) => {
    if (!window.confirm(`Delete "${post.title}"? This cannot be undone.`)) return;
    setError('');
    setNotice('');
    try {
      await api.delete(`/activities/${post.id}`);
      setPosts((items) => items.filter((item) => item.id !== post.id));
      setNotice('The post has been deleted.');
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    }
  };

  const submitComment = async (event, post) => {
    event.preventDefault();
    const content = (commentDrafts[post.id] || '').trim();
    if (!content) return;
    setPostingCommentId(post.id);
    setError('');
    try {
      const response = await api.post(`/activities/${post.id}/comments`, { content });
      setPosts((items) => items.map((item) => (
        item.id === post.id ? { ...item, comments: [...(item.comments || []), response.data] } : item
      )));
      setCommentDrafts((drafts) => ({ ...drafts, [post.id]: '' }));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setPostingCommentId(null);
    }
  };

  const deleteComment = async (post, comment) => {
    if (!window.confirm('Delete this comment?')) return;
    setError('');
    try {
      await api.delete(`/activities/${post.id}/comments/${comment.id}`);
      setPosts((items) => items.map((item) => (
        item.id === post.id
          ? { ...item, comments: item.comments.filter((entry) => entry.id !== comment.id) }
          : item
      )));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    }
  };

  const canDelete = (post) => (
    user?.id === post.author_id || staffRoles.includes(user?.role)
  );
  const canDeleteComment = (comment) => (
    user?.id === comment.author_id || staffRoles.includes(user?.role)
  );

  return (
    <section className="page-stack activities-page">
      <div>
        <p className="eyebrow">Computer Science Department</p>
        <h1 className="page-title">Department activities</h1>
        <p className="page-description">Announcements, events, opportunities, and updates from your college community.</p>
      </div>

      {error && <div className="notice notice-error" role="alert"><AlertCircle size={17} /><span>{error}</span></div>}
      {notice && <div className="notice notice-success" role="status">{notice}</div>}

      <form className="panel activity-compose" onSubmit={submitPost}>
        <div className="activity-compose-heading">
          <MessageSquareText size={19} />
          <h2 className="section-title">Share an update</h2>
        </div>
        <div className="field-grid">
          <label className="field-label">
            Title
            <input
              className="text-input"
              maxLength={180}
              required
              value={form.title}
              onChange={(event) => setForm((value) => ({ ...value, title: event.target.value }))}
            />
          </label>
          <label className="field-label">
            Category
            <select
              className="text-input"
              value={form.category}
              onChange={(event) => setForm((value) => ({ ...value, category: event.target.value }))}
            >
              {categories.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
        <label className="field-label">
          Update
          <textarea
            className="text-input activity-textarea"
            maxLength={10000}
            required
            rows={5}
            value={form.content}
            onChange={(event) => setForm((value) => ({ ...value, content: event.target.value }))}
          />
        </label>
        <div className="activity-compose-actions">
          <label className="attachment-picker">
            <Paperclip size={16} />
            <span>{attachment ? attachment.name : 'Attach image or PDF'}</span>
            <input
              key={fileInputKey}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,application/pdf,image/png,image/jpeg,image/gif,image/webp"
              onChange={(event) => setAttachment(event.target.files?.[0] || null)}
            />
          </label>
          <button className="primary-button" type="submit" disabled={saving}>
            <Send size={15} /> {saving ? 'Sharing…' : 'Share post'}
          </button>
        </div>
        <p className="activity-file-hint">PDF or image attachment, up to 10 MB.</p>
      </form>

      <div className="activity-feed-heading">
        <div>
          <h2 className="section-title">Department feed</h2>
          <p className="page-description">Newest posts appear first.</p>
        </div>
        <label className="activity-filter">
          <span>Filter</span>
          <select
            className="text-input"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">All categories</option>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>

      {loading ? (
        <div className="panel empty-state">Loading department activities…</div>
      ) : posts.length ? (
        <div className="activity-feed">
          {posts.map((post) => (
            <article className="panel activity-card" key={post.id}>
              <div className="activity-card-top">
                <span className={`activity-category category-${post.category.toLowerCase()}`}>{post.category}</span>
                {canDelete(post) && (
                  <button
                    type="button"
                    className="icon-button activity-delete"
                    onClick={() => deletePost(post)}
                    aria-label={`Delete ${post.title}`}
                    title="Delete post"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
              <div className="activity-author">
                <ProfileAvatar name={post.author_name} imageUrl={post.profile_image_url} size={44} />
                <div className="activity-author-copy">
                  <strong>{post.author_name}</strong>
                  <div className="activity-meta">
                    <span className="activity-role">{post.author_role.replace('_', ' ')}</span>
                    <time dateTime={post.created_at}>{formatDate(post.created_at)}</time>
                  </div>
                </div>
              </div>
              <h3 className="activity-title">{post.title}</h3>
              <p className="activity-content">{post.content}</p>
              {post.attachment_filename && (
                <button
                  type="button"
                  className="attachment-download"
                  onClick={() => downloadAttachment(post)}
                >
                  {post.attachment_content_type?.startsWith('image/') ? <Image size={16} /> : <FileText size={16} />}
                  <span>{post.attachment_filename}</span>
                  <Download size={15} />
                </button>
              )}
              <section className="activity-comments" aria-label={`Comments on ${post.title}`}>
                <div className="activity-comments-heading">
                  <MessageSquareText size={16} />
                  <h4>Comments</h4>
                  <span>{post.comments?.length || 0}</span>
                </div>
                {post.comments?.length ? (
                  <div className="activity-comment-list">
                    {post.comments.map((comment) => (
                      <div className="activity-comment" key={comment.id}>
                        <ProfileAvatar
                          name={comment.author_name}
                          imageUrl={comment.profile_image_url}
                          size={34}
                        />
                        <div className="activity-comment-body">
                          <div className="activity-comment-heading">
                            <strong>{comment.author_name}</strong>
                            <span className="activity-role">{comment.author_role.replace('_', ' ')}</span>
                            <time dateTime={comment.created_at}>{formatDate(comment.created_at)}</time>
                            {canDeleteComment(comment) && (
                              <button
                                type="button"
                                className="activity-comment-delete"
                                onClick={() => deleteComment(post, comment)}
                                aria-label={`Delete comment by ${comment.author_name}`}
                              >
                                <Trash2 size={14} />
                              </button>
                            )}
                          </div>
                          <p>{comment.content}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="activity-comments-empty">No comments yet. Start the conversation.</p>
                )}
                <form className="activity-comment-form" onSubmit={(event) => submitComment(event, post)}>
                  <ProfileAvatar name={user?.full_name} imageUrl={user?.profile_image_url} size={34} />
                  <input
                    className="text-input"
                    type="text"
                    maxLength={2000}
                    value={commentDrafts[post.id] || ''}
                    onChange={(event) => setCommentDrafts((drafts) => ({
                      ...drafts,
                      [post.id]: event.target.value,
                    }))}
                    placeholder="Write a comment..."
                    aria-label={`Write a comment on ${post.title}`}
                  />
                  <button
                    type="submit"
                    className="icon-button activity-comment-send"
                    disabled={!commentDrafts[post.id]?.trim() || postingCommentId === post.id}
                    aria-label="Send comment"
                  >
                    <Send size={16} />
                  </button>
                </form>
              </section>
            </article>
          ))}
        </div>
      ) : (
        <div className="panel empty-state">
          {category ? `No ${category.toLowerCase()} posts yet.` : 'No department activities have been posted yet.'}
        </div>
      )}
    </section>
  );
}

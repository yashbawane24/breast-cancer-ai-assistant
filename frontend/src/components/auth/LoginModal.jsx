import { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';
import { X, Mail, Lock, User as UserIcon, Loader2 } from 'lucide-react';
import Translate from '../common/Translate';

export default function LoginModal({ isOpen, onClose }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login, signup } = useAuth();
  const { t } = useLanguage();

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await signup(email, password, fullName);
      }
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail) {
        setError(detail);
      } else if (err.response?.status === 500) {
        setError('Server error: Database connection failed. Please check backend settings.');
      } else if (!err.response) {
        setError('Network error: Unable to reach the server.');
      } else {
        setError('An error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink/40 backdrop-blur-sm">
      <div className="relative w-full max-w-md bg-white/80 backdrop-blur-md border border-white/40 shadow-2xl rounded-2xl overflow-hidden">
        {/* Decorative blobs */}
        <div className="absolute top-0 -left-10 w-40 h-40 bg-rose-400/20 rounded-full blur-3xl mix-blend-multiply pointer-events-none" />
        <div className="absolute bottom-0 -right-10 w-40 h-40 bg-blue-400/20 rounded-full blur-3xl mix-blend-multiply pointer-events-none" />

        <div className="relative p-6 sm:p-8">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 text-ink-soft hover:text-ink hover:bg-black/5 rounded-full transition-colors"
          >
            <X size={20} />
          </button>

          <div className="text-center mb-8">
            <h2 className="text-2xl font-display font-semibold text-ink">
              <Translate>{isLogin ? 'Welcome back' : 'Create an account'}</Translate>
            </h2>
            <p className="text-sm text-ink-soft mt-2">
              <Translate>
                {isLogin ? 'Sign in to access your medical insights.' : 'Join Halcyon to take control of your health data.'}
              </Translate>
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <UserIcon size={18} className="text-ink-soft" />
                </div>
                <input
                  type="text"
                  placeholder={t('Full Name')}
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-white/50 border border-ink/10 rounded-xl text-ink placeholder-ink-soft focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
                />
              </div>
            )}
            
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Mail size={18} className="text-ink-soft" />
              </div>
              <input
                type="email"
                placeholder={t('Email address')}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white/50 border border-ink/10 rounded-xl text-ink placeholder-ink-soft focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
              />
            </div>

            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock size={18} className="text-ink-soft" />
              </div>
              <input
                type="password"
                placeholder={t('Password')}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white/50 border border-ink/10 rounded-xl text-ink placeholder-ink-soft focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 transition-all"
              />
            </div>

            {error && (
              <div className="p-3 bg-red-50 text-red-600 text-sm rounded-xl border border-red-100">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-ink text-white font-medium rounded-xl hover:bg-ink-light focus:outline-none focus:ring-4 focus:ring-ink/10 transition-all disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
            >
              {loading && <Loader2 size={18} className="animate-spin" />}
              <Translate>{isLogin ? 'Sign In' : 'Create Account'}</Translate>
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-ink-soft">
            <Translate>{isLogin ? "Don't have an account? " : "Already have an account? "}</Translate>
            <button
              onClick={() => {
                setIsLogin(!isLogin);
                setError('');
              }}
              className="text-rose-500 hover:text-rose-600 font-medium transition-colors"
            >
              <Translate>{isLogin ? 'Sign up' : 'Sign in'}</Translate>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

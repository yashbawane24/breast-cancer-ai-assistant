import { createContext, useContext, useState, useEffect } from 'react';
import { login as apiLogin, signup as apiSignup, getMe } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const res = await getMe();
          setUser(res.data);
        } catch (err) {
          localStorage.removeItem('token');
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email, password) => {
    const res = await apiLogin(email, password);
    localStorage.setItem('token', res.data.access_token);
    if (res.data.user) {
      setUser(res.data.user);
    } else {
      const userRes = await getMe();
      setUser(userRes.data);
    }
  };

  const signup = async (email, password, fullName) => {
    await apiSignup(email, password, fullName);
    const loginRes = await apiLogin(email, password);
    localStorage.setItem('token', loginRes.data.access_token);
    const userRes = await getMe();
    setUser(userRes.data);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

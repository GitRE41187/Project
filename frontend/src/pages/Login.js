import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'react-toastify';
import { User, Lock, Eye, EyeOff, Facebook, Twitter, Mail, ArrowRight, Sparkles } from 'lucide-react';

const Login = () => {
  const [formData, setFormData] = useState({
    username: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const { login } = useAuth();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const result = await login(formData.username, formData.password);
    
    if (result.success) {
      toast.success('Login successful!');
    } else {
      toast.error(result.error);
    }
    
    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #f0f9ff 0%, #ffffff 50%, #f0fdfa 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background Elements */}
      <div style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        zIndex: 0
      }}>
        <div style={{
          position: 'absolute',
          top: '-10rem',
          right: '-10rem',
          width: '20rem',
          height: '20rem',
          background: '#c084fc',
          borderRadius: '50%',
          mixBlendMode: 'multiply',
          filter: 'blur(40px)',
          opacity: 0.7,
          animation: 'blob 7s infinite'
        }}></div>
        <div style={{
          position: 'absolute',
          bottom: '-10rem',
          left: '-10rem',
          width: '20rem',
          height: '20rem',
          background: '#fbbf24',
          borderRadius: '50%',
          mixBlendMode: 'multiply',
          filter: 'blur(40px)',
          opacity: 0.7,
          animation: 'blob 7s infinite 2s'
        }}></div>
        <div style={{
          position: 'absolute',
          top: '10rem',
          left: '10rem',
          width: '20rem',
          height: '20rem',
          background: '#f472b6',
          borderRadius: '50%',
          mixBlendMode: 'multiply',
          filter: 'blur(40px)',
          opacity: 0.7,
          animation: 'blob 7s infinite 4s'
        }}></div>
      </div>

      <div style={{
        position: 'relative',
        width: '100%',
        maxWidth: '72rem',
        margin: '0 auto',
        zIndex: 1
      }}>
        <div style={{
          background: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(20px)',
          borderRadius: '1.5rem',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '600px'
        }}>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            minHeight: '600px'
          }}>
            {/* Left Side - Hero Section */}
            <div style={{
              flex: '1',
              background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #ec4899 100%)',
              padding: '3rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              position: 'relative',
              overflow: 'hidden'
            }}>
              {/* Background Pattern */}
              <div style={{
                position: 'absolute',
                inset: 0,
                opacity: 0.1,
                backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.1'%3E%3Ccircle cx='30' cy='30' r='4'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
              }}></div>
              
              <div style={{
                position: 'relative',
                zIndex: 10,
                color: 'white'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: '1.5rem'
                }}>
                  <div style={{
                    width: '3rem',
                    height: '3rem',
                    background: 'rgba(255, 255, 255, 0.2)',
                    borderRadius: '0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginRight: '1rem'
                  }}>
                    <Sparkles size={24} color="white" />
                  </div>
                  <h1 style={{
                    fontSize: '1.5rem',
                    fontWeight: 'bold'
                  }}>Welcome Back</h1>
                </div>
                
                <h2 style={{
                  fontSize: '2.5rem',
                  fontWeight: 'bold',
                  marginBottom: '1.5rem',
                  lineHeight: '1.2'
                }}>
                  Sign in to your
                  <span style={{
                    display: 'block',
                    background: 'linear-gradient(90deg, #fbbf24, #f472b6)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text'
                  }}>
                    Dashboard
                  </span>
                </h2>
                
                <p style={{
                  fontSize: '1.25rem',
                  color: 'rgba(255, 255, 255, 0.9)',
                  marginBottom: '2rem',
                  lineHeight: '1.6'
                }}>
                  Access your personalized workspace and manage your projects with ease. 
                  Join thousands of users who trust our platform.
                </p>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255, 255, 255, 0.8)' }}>
                    <div style={{
                      width: '0.5rem',
                      height: '0.5rem',
                      background: '#4ade80',
                      borderRadius: '50%',
                      marginRight: '0.75rem'
                    }}></div>
                    <span>Secure and encrypted</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255, 255, 255, 0.8)' }}>
                    <div style={{
                      width: '0.5rem',
                      height: '0.5rem',
                      background: '#60a5fa',
                      borderRadius: '50%',
                      marginRight: '0.75rem'
                    }}></div>
                    <span>24/7 customer support</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255, 255, 255, 0.8)' }}>
                    <div style={{
                      width: '0.5rem',
                      height: '0.5rem',
                      background: '#a78bfa',
                      borderRadius: '50%',
                      marginRight: '0.75rem'
                    }}></div>
                    <span>Advanced analytics</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Side - Login Form */}
            <div style={{
              flex: '1',
              padding: '3rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center'
            }}>
              <div style={{
                maxWidth: '28rem',
                margin: '0 auto',
                width: '100%'
              }}>
                <div style={{
                  textAlign: 'center',
                  marginBottom: '2rem'
                }}>
                  <h3 style={{
                    fontSize: '1.875rem',
                    fontWeight: 'bold',
                    color: '#111827',
                    marginBottom: '0.5rem'
                  }}>Welcome back!</h3>
                  <p style={{ color: '#6b7280' }}>Please sign in to your account</p>
                </div>

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ position: 'relative' }}>
                      <div style={{
                        position: 'absolute',
                        top: '50%',
                        left: '1rem',
                        transform: 'translateY(-50%)',
                        display: 'flex',
                        alignItems: 'center',
                        pointerEvents: 'none'
                      }}>
                        <User size={20} color="#9ca3af" />
                      </div>
                      <input
                        id="username"
                        name="username"
                        type="text"
                        required
                        style={{
                          width: '100%',
                          paddingLeft: '3rem',
                          paddingRight: '1rem',
                          paddingTop: '1rem',
                          paddingBottom: '1rem',
                          border: '1px solid #e5e7eb',
                          borderRadius: '0.75rem',
                          fontSize: '1rem',
                          background: '#f9fafb',
                          transition: 'all 0.2s ease',
                          outline: 'none'
                        }}
                        onFocus={(e) => {
                          e.target.style.background = 'white';
                          e.target.style.borderColor = '#4f46e5';
                          e.target.style.boxShadow = '0 0 0 3px rgba(79, 70, 229, 0.1)';
                        }}
                        onBlur={(e) => {
                          e.target.style.background = '#f9fafb';
                          e.target.style.borderColor = '#e5e7eb';
                          e.target.style.boxShadow = 'none';
                        }}
                        placeholder="Username"
                        value={formData.username}
                        onChange={handleChange}
                      />
                    </div>
                    
                    <div style={{ position: 'relative' }}>
                      <div style={{
                        position: 'absolute',
                        top: '50%',
                        left: '1rem',
                        transform: 'translateY(-50%)',
                        display: 'flex',
                        alignItems: 'center',
                        pointerEvents: 'none'
                      }}>
                        <Lock size={20} color="#9ca3af" />
                      </div>
                      <input
                        id="password"
                        name="password"
                        type={showPassword ? 'text' : 'password'}
                        required
                        style={{
                          width: '100%',
                          paddingLeft: '3rem',
                          paddingRight: '3rem',
                          paddingTop: '1rem',
                          paddingBottom: '1rem',
                          border: '1px solid #e5e7eb',
                          borderRadius: '0.75rem',
                          fontSize: '1rem',
                          background: '#f9fafb',
                          transition: 'all 0.2s ease',
                          outline: 'none'
                        }}
                        onFocus={(e) => {
                          e.target.style.background = 'white';
                          e.target.style.borderColor = '#4f46e5';
                          e.target.style.boxShadow = '0 0 0 3px rgba(79, 70, 229, 0.1)';
                        }}
                        onBlur={(e) => {
                          e.target.style.background = '#f9fafb';
                          e.target.style.borderColor = '#e5e7eb';
                          e.target.style.boxShadow = 'none';
                        }}
                        placeholder="Password"
                        value={formData.password}
                        onChange={handleChange}
                      />
                      <button
                        type="button"
                        style={{
                          position: 'absolute',
                          top: '50%',
                          right: '1rem',
                          transform: 'translateY(-50%)',
                          display: 'flex',
                          alignItems: 'center',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer'
                        }}
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? (
                          <EyeOff size={20} color="#9ca3af" />
                        ) : (
                          <Eye size={20} color="#9ca3af" />
                        )}
                      </button>
                    </div>
                  </div>

                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <label style={{ display: 'flex', alignItems: 'center' }}>
                      <input
                        type="checkbox"
                        checked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                        style={{
                          width: '1rem',
                          height: '1rem',
                          accentColor: '#4f46e5',
                          marginRight: '0.5rem'
                        }}
                      />
                      <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>Remember me</span>
                    </label>
                    <Link
                      to="/forgot-password"
                      style={{
                        fontSize: '0.875rem',
                        color: '#4f46e5',
                        textDecoration: 'none',
                        fontWeight: '500'
                      }}
                    >
                      Forgot password?
                    </Link>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    style={{
                      width: '100%',
                      background: 'linear-gradient(90deg, #4f46e5, #7c3aed)',
                      color: 'white',
                      padding: '1rem 1.5rem',
                      borderRadius: '0.75rem',
                      fontSize: '1.125rem',
                      fontWeight: '600',
                      border: 'none',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      opacity: loading ? 0.5 : 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.2s ease'
                    }}
                    onMouseEnter={(e) => {
                      if (!loading) {
                        e.target.style.background = 'linear-gradient(90deg, #4338ca, #6d28d9)';
                        e.target.style.transform = 'scale(1.02)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!loading) {
                        e.target.style.background = 'linear-gradient(90deg, #4f46e5, #7c3aed)';
                        e.target.style.transform = 'scale(1)';
                      }
                    }}
                  >
                    {loading ? (
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <div style={{
                          width: '1.25rem',
                          height: '1.25rem',
                          border: '2px solid transparent',
                          borderTop: '2px solid white',
                          borderRadius: '50%',
                          animation: 'spin 1s linear infinite',
                          marginRight: '0.5rem'
                        }}></div>
                        Signing in...
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        Sign In
                        <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} />
                      </div>
                    )}
                  </button>
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ color: '#6b7280' }}>
                      Don't have an account?{' '}
                      <Link
                        to="/register"
                        style={{
                          color: '#4f46e5',
                          textDecoration: 'none',
                          fontWeight: '600'
                        }}
                      >
                        Sign up for free
                      </Link>
                    </p>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;

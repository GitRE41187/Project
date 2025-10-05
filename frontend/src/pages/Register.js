import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'react-toastify';
import { User, Mail, Lock, Eye, EyeOff, Facebook, Twitter, ArrowRight, Sparkles, CheckCircle } from 'lucide-react';

const Register = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (formData.password !== formData.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    setLoading(true);

    const result = await register(formData.username, formData.email, formData.password);
    
    if (result.success) {
      toast.success('Registration successful!');
    } else {
      toast.error(result.error);
    }
    
    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #faf5ff 0%, #ffffff 50%, #fdf2f8 100%)',
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
          background: '#60a5fa',
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
          background: '#c084fc',
          borderRadius: '50%',
          mixBlendMode: 'multiply',
          filter: 'blur(40px)',
          opacity: 0.7,
          animation: 'blob 7s infinite 2s'
        }}></div>
        <div style={{
          position: 'absolute',
          top: '10rem',
          right: '10rem',
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
          minHeight: '700px'
        }}>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            minHeight: '700px'
          }}>
            {/* Left Side - Hero Section */}
            <div style={{
              flex: '1',
              background: 'linear-gradient(135deg, #7c3aed 0%, #ec4899 50%, #ef4444 100%)',
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
                  }}>Join Us Today</h1>
                </div>
                
                <h2 style={{
                  fontSize: '2.5rem',
                  fontWeight: 'bold',
                  marginBottom: '1.5rem',
                  lineHeight: '1.2'
                }}>
                  Create your
                  <span style={{
                    display: 'block',
                    background: 'linear-gradient(90deg, #fbbf24, #f97316)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text'
                  }}>
                    Free Account
                  </span>
                </h2>
                
                <p style={{
                  fontSize: '1.25rem',
                  color: 'rgba(255, 255, 255, 0.9)',
                  marginBottom: '2rem',
                  lineHeight: '1.6'
                }}>
                  Start your journey with us and unlock powerful features to manage your projects, 
                  collaborate with teams, and achieve your goals.
                </p>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255, 255, 255, 0.8)' }}>
                    <CheckCircle size={20} color="#4ade80" style={{ marginRight: '0.75rem' }} />
                    <span>Free forever plan available</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255, 255, 255, 0.8)' }}>
                    <CheckCircle size={20} color="#4ade80" style={{ marginRight: '0.75rem' }} />
                    <span>No credit card required</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', color: 'rgba(255, 255, 255, 0.8)' }}>
                    <CheckCircle size={20} color="#4ade80" style={{ marginRight: '0.75rem' }} />
                    <span>Setup in under 2 minutes</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Side - Register Form */}
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
                  }}>Create Account</h3>
                  <p style={{ color: '#6b7280' }}>Fill in your details to get started</p>
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
                          e.target.style.borderColor = '#7c3aed';
                          e.target.style.boxShadow = '0 0 0 3px rgba(124, 58, 237, 0.1)';
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
                        <Mail size={20} color="#9ca3af" />
                      </div>
                      <input
                        id="email"
                        name="email"
                        type="email"
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
                          e.target.style.borderColor = '#7c3aed';
                          e.target.style.boxShadow = '0 0 0 3px rgba(124, 58, 237, 0.1)';
                        }}
                        onBlur={(e) => {
                          e.target.style.background = '#f9fafb';
                          e.target.style.borderColor = '#e5e7eb';
                          e.target.style.boxShadow = 'none';
                        }}
                        placeholder="Email address"
                        value={formData.email}
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
                          e.target.style.borderColor = '#7c3aed';
                          e.target.style.boxShadow = '0 0 0 3px rgba(124, 58, 237, 0.1)';
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
                        id="confirmPassword"
                        name="confirmPassword"
                        type={showConfirmPassword ? 'text' : 'password'}
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
                          e.target.style.borderColor = '#7c3aed';
                          e.target.style.boxShadow = '0 0 0 3px rgba(124, 58, 237, 0.1)';
                        }}
                        onBlur={(e) => {
                          e.target.style.background = '#f9fafb';
                          e.target.style.borderColor = '#e5e7eb';
                          e.target.style.boxShadow = 'none';
                        }}
                        placeholder="Confirm password"
                        value={formData.confirmPassword}
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
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      >
                        {showConfirmPassword ? (
                          <EyeOff size={20} color="#9ca3af" />
                        ) : (
                          <Eye size={20} color="#9ca3af" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Password Requirements */}
                  <div style={{
                    background: '#f9fafb',
                    borderRadius: '0.75rem',
                    padding: '1rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem'
                  }}>
                    <p style={{
                      fontSize: '0.875rem',
                      fontWeight: '500',
                      color: '#374151',
                      marginBottom: '0.5rem'
                    }}>Password requirements:</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: '0.875rem',
                        color: formData.password.length >= 6 ? '#059669' : '#6b7280'
                      }}>
                        <CheckCircle size={16} color={formData.password.length >= 6 ? '#10b981' : '#9ca3af'} style={{ marginRight: '0.5rem' }} />
                        At least 6 characters
                      </div>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: '0.875rem',
                        color: (formData.password === formData.confirmPassword && formData.password) ? '#059669' : '#6b7280'
                      }}>
                        <CheckCircle size={16} color={(formData.password === formData.confirmPassword && formData.password) ? '#10b981' : '#9ca3af'} style={{ marginRight: '0.5rem' }} />
                        Passwords match
                      </div>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    style={{
                      width: '100%',
                      background: 'linear-gradient(90deg, #7c3aed, #ec4899)',
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
                        e.target.style.background = 'linear-gradient(90deg, #6d28d9, #db2777)';
                        e.target.style.transform = 'scale(1.02)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!loading) {
                        e.target.style.background = 'linear-gradient(90deg, #7c3aed, #ec4899)';
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
                        Creating account...
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        Create Account
                        <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} />
                      </div>
                    )}
                  </button>

                  <div style={{ textAlign: 'center' }}>
                    <p style={{ color: '#6b7280' }}>
                      Already have an account?{' '}
                      <Link
                        to="/login"
                        style={{
                          color: '#7c3aed',
                          textDecoration: 'none',
                          fontWeight: '600'
                        }}
                      >
                        Sign in here
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

export default Register;

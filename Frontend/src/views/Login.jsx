import React, { useState } from 'react';
import { login, register } from '../api';
import Icon from '../components/Icon';
import { errorMessages } from '../format';

const HIGHLIGHTS = [
  'See which lab kit and sports gear is free for your dates',
  'Reserve in seconds, then collect it from the desk',
  'Track what you have out and when it is due back',
];

const EMPTY_FORM = {
  username: '', password: '', email: '', first_name: '', last_name: '', student_number: '', course: '', year: '',
};

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('signin');
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const signingIn = mode === 'signin';

  const update = field => event => setForm({ ...form, [field]: event.target.value });

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setErrors([]);
    try {
      if (signingIn) {
        await login(form.username, form.password);
      } else {
        await register({ ...form, year: form.year ? Number(form.year) : null });
      }
    } catch (err) {
      if (err.status === 429) {
        setErrors(['Too many attempts. Please wait a minute and try again.']);
      } else {
        setErrors(signingIn ? ['Invalid username or password.'] : errorMessages(err));
      }
      setSubmitting(false);
      return;
    }
    onLogin();
  }

  function switchMode() {
    setMode(signingIn ? 'register' : 'signin');
    setErrors([]);
  }

  return (
    <div className="auth-layout">
      <aside className="auth-panel">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><Icon name="cap" size={18} /></span>
          <span>Campus Equipment Rental</span>
        </div>
        <p className="auth-headline">Borrow the kit, get on with the work.</p>
        <ul className="auth-highlights">
          {HIGHLIGHTS.map(text => (
            <li key={text}><Icon name="check" size={18} />{text}</li>
          ))}
        </ul>
      </aside>
      <form className="login card" onSubmit={handleSubmit}>
        <h2>{signingIn ? 'Sign in to Campus Equipment Rental' : 'Create your student account'}</h2>
        <p className="muted">Reserve lab and sports equipment and keep track of your rentals.</p>
        <label>
          Username
          <input value={form.username} onChange={update('username')} autoComplete="username" required />
        </label>
        {!signingIn && (
          <>
            <label>
              Email
              <input type="email" value={form.email} onChange={update('email')} autoComplete="email" required />
            </label>
            <div className="name-fields">
              <label>
                First name
                <input value={form.first_name} onChange={update('first_name')} autoComplete="given-name" required />
              </label>
              <label>
                Last name
                <input value={form.last_name} onChange={update('last_name')} autoComplete="family-name" required />
              </label>
            </div>
            <label>
              Student number
              <input value={form.student_number} onChange={update('student_number')} required />
            </label>
            <div className="name-fields">
              <label>
                Course
                <input value={form.course} onChange={update('course')} placeholder="e.g. BSc Physics" required />
              </label>
              <label>
                Year
                <select value={form.year} onChange={update('year')} required>
                  <option value="">Choose</option>
                  {[1, 2, 3, 4, 5, 6, 7].map(year => <option key={year} value={year}>Year {year}</option>)}
                </select>
              </label>
            </div>
          </>
        )}
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={update('password')}
            autoComplete={signingIn ? 'current-password' : 'new-password'}
            required
          />
        </label>
        {errors.map(message => <p key={message} className="error">{message}</p>)}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Please wait...' : signingIn ? 'Sign in' : 'Create account'}
        </button>
        <button type="button" className="link" onClick={switchMode}>
          {signingIn ? 'New student? Create an account' : 'Already registered? Sign in'}
        </button>
      </form>
    </div>
  );
}

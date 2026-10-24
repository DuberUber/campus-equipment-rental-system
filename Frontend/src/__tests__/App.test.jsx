import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

const EMPTY_PAGE = { count: 0, next: null, previous: null, results: [] };
const STUDENT = {
  id: 7, username: 'aoife', full_name: 'Aoife Brennan', email: 'aoife@example.com', student_number: 'S21000101',
  is_staff: false, role: 'student',
};
const STAFF = { ...STUDENT, id: 2, username: 'desk', full_name: 'Equipment Desk', student_number: null, is_staff: true, role: 'staff' };
const TOKEN_KEY = 'equipmentrental.authToken';

function jsonResponse(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
}

// Answer auth calls explicitly and every list endpoint with an empty page.
function mockApi({ me = STUDENT, token = 'abc123', pages = {} } = {}) {
  global.fetch.mockImplementation(url => {
    if (url.endsWith('/auth/token/')) return jsonResponse({ token });
    if (url.endsWith('/auth/register/')) return jsonResponse({ token, user: me }, 201);
    if (url.endsWith('/auth/me/')) return jsonResponse(me);
    const match = Object.keys(pages).find(fragment => url.includes(fragment));
    return jsonResponse(match ? { ...EMPTY_PAGE, count: pages[match].length, results: pages[match] } : EMPTY_PAGE);
  });
}

function fill(label, value) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </MemoryRouter>,
  );
}

function signedIn(me) {
  localStorage.setItem(TOKEN_KEY, 'abc123');
  mockApi({ me });
}

const navLinks = () => within(screen.getByRole('navigation', { name: 'Main' })).getAllByRole('link').map(link => link.textContent);

beforeEach(() => {
  localStorage.clear();
  global.fetch = jest.fn();
});

test('asks for credentials when there is no token', () => {
  renderApp();
  expect(screen.getByRole('heading', { name: /sign in to campus equipment rental/i })).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('signing in stores the token and opens the equipment catalogue', async () => {
  mockApi();

  renderApp();
  fill(/username/i, 'aoife');
  fill(/password/i, 'secret');
  fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));

  expect(await screen.findByRole('heading', { name: 'Browse equipment' })).toBeInTheDocument();
  expect(localStorage.getItem(TOKEN_KEY)).toBe('abc123');
  await waitFor(() => {
    const listCall = global.fetch.mock.calls.find(([url]) => url.includes('/equipment/?'));
    expect(listCall[0]).toMatch(/kind=lab/);
    expect(listCall[1].headers.Authorization).toBe('Token abc123');
  });
});

test('new students can create an account', async () => {
  mockApi();

  renderApp();
  fireEvent.click(screen.getByRole('button', { name: /create an account/i }));
  fill(/username/i, 'aoife');
  fill(/email/i, 'aoife@example.com');
  fill(/first name/i, 'Aoife');
  fill(/last name/i, 'Brennan');
  fill(/student number/i, 'S21000101');
  fill(/course/i, 'BSc Physics');
  fill(/year/i, '3');
  fill(/password/i, 'correct-horse-battery-staple');
  fireEvent.click(screen.getByRole('button', { name: /^create account$/i }));

  expect(await screen.findByRole('heading', { name: 'Browse equipment' })).toBeInTheDocument();
  const [, options] = global.fetch.mock.calls.find(([url]) => url.endsWith('/auth/register/'));
  expect(JSON.parse(options.body)).toMatchObject({
    username: 'aoife', email: 'aoife@example.com', student_number: 'S21000101', course: 'BSc Physics', year: 3,
  });
  expect(localStorage.getItem(TOKEN_KEY)).toBe('abc123');
});

test('shows registration errors from the API', async () => {
  global.fetch.mockImplementation(() => jsonResponse({ student_number: ['An account with this student number already exists.'] }, 400));

  renderApp();
  fireEvent.click(screen.getByRole('button', { name: /create an account/i }));
  fill(/username/i, 'aoife');
  fill(/email/i, 'aoife@example.com');
  fill(/first name/i, 'Aoife');
  fill(/last name/i, 'Brennan');
  fill(/student number/i, 'S21000101');
  fill(/course/i, 'BSc Physics');
  fill(/year/i, '3');
  fill(/password/i, 'correct-horse-battery-staple');
  fireEvent.click(screen.getByRole('button', { name: /^create account$/i }));

  expect(await screen.findByText('student number: An account with this student number already exists.')).toBeInTheDocument();
});

test('shows an error for bad credentials', async () => {
  global.fetch.mockImplementation(() => jsonResponse({ non_field_errors: ['Unable to log in.'] }, 400));

  renderApp();
  fill(/username/i, 'aoife');
  fill(/password/i, 'wrong');
  fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));

  expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
  expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
});

test('an expired token sends the user back to the sign-in screen', async () => {
  localStorage.setItem(TOKEN_KEY, 'expired');
  global.fetch.mockImplementation(() => jsonResponse({ detail: 'Invalid token.' }, 401));

  renderApp('/rentals');

  expect(await screen.findByRole('heading', { name: /sign in to campus equipment rental/i })).toBeInTheDocument();
  expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
});

test('students get the student navigation and their rentals', async () => {
  signedIn(STUDENT);

  renderApp('/rentals');

  expect(await screen.findByRole('heading', { name: 'My rentals' })).toBeInTheDocument();
  expect(await screen.findByText('Nothing out with you right now.')).toBeInTheDocument();
  expect(navLinks()).toEqual(['Browse equipment', 'My rentals']);
  const historyCall = global.fetch.mock.calls.find(([url]) => url.includes('/me/history/?when='));
  expect(historyCall[0]).toMatch(/when=current&ordering=due_at/);
});

test('staff get the desk navigation and land on the equipment desk', async () => {
  signedIn(STAFF);

  renderApp('/');

  expect(await screen.findByRole('heading', { name: 'Equipment desk' })).toBeInTheDocument();
  expect(navLinks()).toEqual(['Equipment desk', 'Overdue', 'Browse equipment', 'Manage equipment', 'Students', 'Admin']);
  expect(screen.getByRole('heading', { name: /pickups/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /returns due/i })).toBeInTheDocument();
});

test('students who open a staff page are sent to the catalogue', async () => {
  for (const path of ['/desk', '/overdue', '/students', '/students/3', '/manage-equipment']) {
    signedIn(STUDENT);
    const { unmount } = renderApp(path);
    // eslint-disable-next-line no-await-in-loop
    expect(await screen.findByRole('heading', { name: 'Browse equipment' })).toBeInTheDocument();
    unmount();
  }
});

test('staff who open the student rentals page are sent to the desk', async () => {
  signedIn(STAFF);

  renderApp('/rentals');

  expect(await screen.findByRole('heading', { name: 'Equipment desk' })).toBeInTheDocument();
});

test('logging out returns to the sign-in screen and the next user starts at their home page', async () => {
  signedIn(STAFF);
  renderApp('/students');
  expect(await screen.findByRole('heading', { name: 'Students' })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Log out' }));
  expect(await screen.findByRole('heading', { name: /sign in to campus equipment rental/i })).toBeInTheDocument();
  expect(localStorage.getItem(TOKEN_KEY)).toBeNull();

  mockApi();
  fill(/username/i, 'aoife');
  fill(/password/i, 'secret');
  fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));

  expect(await screen.findByRole('heading', { name: 'Browse equipment' })).toBeInTheDocument();
});

test('the browse page lists only items free for the chosen dates', async () => {
  signedIn(STUDENT);
  renderApp('/equipment');
  await screen.findByRole('heading', { name: 'Browse equipment' });

  fireEvent.click(screen.getByRole('button', { name: 'Next 3 days' }));

  await waitFor(() => {
    const call = global.fetch.mock.calls.map(([url]) => url).find(url => url.includes('available_from='));
    expect(call).toMatch(/available_from=[^&]+&available_to=[^&]+/);
  });
  expect(await screen.findByRole('heading', { name: /lab equipment free from/i })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('tab', { name: /sports/i }));
  await waitFor(() => {
    const urls = global.fetch.mock.calls.map(([url]) => url);
    expect(urls.some(url => url.includes('/equipment/?kind=sports'))).toBe(true);
  });
});

import { useEffect, useMemo, useState } from 'react';
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { ADMIN_URL, auth, logout } from './api';
import Avatar from './components/Avatar';
import Icon from './components/Icon';
import LoadState from './components/LoadState';
import { useApi } from './hooks';
import { SessionContext, homePath, isStaff } from './session';
import BrowseEquipment from './views/BrowseEquipment';
import EquipmentDesk from './views/EquipmentDesk';
import EquipmentDetail from './views/EquipmentDetail';
import Login from './views/Login';
import ManageEquipment from './views/ManageEquipment';
import MyRentals from './views/MyRentals';
import NotFound from './views/NotFound';
import OverdueList from './views/OverdueList';
import ReservationDetail from './views/ReservationDetail';
import StudentHistory from './views/StudentHistory';
import StudentList from './views/StudentList';

export default function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(auth.getToken()));

  useEffect(() => {
    const handleLogout = () => setAuthenticated(false);
    window.addEventListener('auth:logout', handleLogout);
    return () => window.removeEventListener('auth:logout', handleLogout);
  }, []);

  if (!authenticated) {
    return <Login onLogin={() => setAuthenticated(true)} />;
  }
  return <SignedInApp onLogout={() => setAuthenticated(false)} />;
}

function SignedInApp({ onLogout }) {
  const navigate = useNavigate();
  // The current user decides which pages are available (student or desk staff).
  const { data: user, error, reload } = useApi('/auth/me/');
  const session = useMemo(() => ({ user, reload }), [user, reload]);

  async function handleLogout() {
    await logout();
    // The next person to sign in starts from their own home page, not this user's last page.
    navigate('/', { replace: true });
    onLogout();
  }

  if (!user) {
    return <main className="content"><LoadState loading={!error} error={error} /></main>;
  }

  const staff = isStaff(user);
  const home = homePath(user);
  // Pages outside the user's role send them to their home page.
  const staffOnly = element => (staff ? element : <Navigate to={home} replace />);
  const studentOnly = element => (staff ? <Navigate to={home} replace /> : element);

  return (
    <SessionContext.Provider value={session}>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true"><Icon name="cap" size={18} /></span>
            <span>Campus Equipment Rental</span>
          </div>
          <nav className="side-nav" aria-label="Main">
            {staff ? (
              <>
                <NavLink to="/desk"><Icon name="desk" />Equipment desk</NavLink>
                <NavLink to="/overdue"><Icon name="alert" />Overdue</NavLink>
                <NavLink to="/equipment"><Icon name="search" />Browse equipment</NavLink>
                <NavLink to="/manage-equipment"><Icon name="wrench" />Manage equipment</NavLink>
                <NavLink to="/students"><Icon name="users" />Students</NavLink>
                <a href={ADMIN_URL}><Icon name="settings" />Admin</a>
              </>
            ) : (
              <>
                <NavLink to="/equipment"><Icon name="search" />Browse equipment</NavLink>
                <NavLink to="/rentals"><Icon name="box" />My rentals</NavLink>
              </>
            )}
          </nav>
          <div className="sidebar-user">
            <Avatar name={user.full_name} size="sm" />
            <span className="user-name" title={user.email}>
              {user.full_name}
              <small>{staff ? 'Desk staff' : `Student${user.student_number ? ` · ${user.student_number}` : ''}`}</small>
            </span>
            <button type="button" className="icon-button" onClick={handleLogout}>
              <Icon name="logout" size={18} />
              <span>Log out</span>
            </button>
          </div>
        </aside>
        <main className="content">
          <Routes>
            <Route path="/" element={<Navigate to={home} replace />} />
            <Route path="/equipment" element={<BrowseEquipment />} />
            <Route path="/equipment/:id" element={<EquipmentDetail />} />
            <Route path="/reservations/:id" element={<ReservationDetail />} />
            <Route path="/rentals" element={studentOnly(<MyRentals />)} />
            <Route path="/desk" element={staffOnly(<EquipmentDesk />)} />
            <Route path="/overdue" element={staffOnly(<OverdueList />)} />
            <Route path="/manage-equipment" element={staffOnly(<ManageEquipment />)} />
            <Route path="/students" element={staffOnly(<StudentList />)} />
            <Route path="/students/:id" element={staffOnly(<StudentHistory />)} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </div>
    </SessionContext.Provider>
  );
}

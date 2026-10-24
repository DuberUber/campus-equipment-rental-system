import { createContext, useContext } from 'react';

// The signed-in user (from /auth/me/) and a way to refresh it.
export const SessionContext = createContext({ user: null, reload: () => {} });

export const useSession = () => useContext(SessionContext);

// Two roles: desk staff (is_staff) run the equipment desk; everyone else is a student.
export const isStaff = user => Boolean(user?.is_staff);
export const isStudent = user => Boolean(user) && !user.is_staff;

// Where each role lands after signing in.
export const homePath = user => (isStaff(user) ? '/desk' : '/equipment');

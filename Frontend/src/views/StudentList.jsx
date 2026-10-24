import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import LoadState from '../components/LoadState';
import Pagination from '../components/Pagination';
import { buildQuery, useDebouncedValue, usePaginatedList } from '../hooks';

export default function StudentList() {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);
  const { rows: students, count, page, setPage, loading, error } = usePaginatedList(
    `/students/${buildQuery({ search: debouncedSearch, ordering: 'last_name' })}`,
  );

  return (
    <div>
      <h2>Students</h2>
      <div className="filters">
        <input
          type="search"
          placeholder="Search by name, student number, email or course..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          aria-label="Search students"
        />
      </div>
      <LoadState loading={loading && students.length === 0} error={error}>
        <p className="muted">{count} student{count === 1 ? '' : 's'}</p>
        <table>
          <thead>
            <tr><th>Name</th><th>Student number</th><th>Course</th><th>Year</th><th>Active</th><th>Overdue</th></tr>
          </thead>
          <tbody>
            {students.map(s => (
              <tr key={s.id} className={s.overdue_reservations ? 'overdue' : ''}>
                <td><Link to={`/students/${s.id}`}>{s.last_name ? `${s.last_name}, ${s.first_name}` : s.full_name}</Link></td>
                <td>{s.student_number}</td>
                <td>{s.course}</td>
                <td>{s.year}</td>
                <td>{s.active_reservations}</td>
                <td>{s.overdue_reservations ? <strong className="overdue-text">{s.overdue_reservations}</strong> : 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination page={page} count={count} onChange={setPage} />
      </LoadState>
    </div>
  );
}

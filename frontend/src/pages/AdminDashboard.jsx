import React, { useEffect, useState } from 'react';

function AdminDashboard({ user, token, onLogout, apiUrl }) {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    const fetchUsers = async () => {
      const res = await fetch(`${apiUrl}/admins/${user.id}/users`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    };
    fetchUsers();
  }, [user, token, apiUrl]);

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">Welcome, Admin {user.name}</h2>
      <button onClick={onLogout} className="bg-red-500 text-white p-2 rounded mb-4">Logout</button>
      <h3 className="text-xl font-semibold mb-2">All Users:</h3>
      <ul>
        {users.map(u => (
          <li key={u.id}>{u.name} - {u.email} - {u.role}</li>
        ))}
      </ul>
    </div>
  );
}

export default AdminDashboard;

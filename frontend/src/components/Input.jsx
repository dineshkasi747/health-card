import React from 'react';

export default function Input({ label, type = 'text', value, onChange, placeholder }) {
  return (
    <div className="mb-4">
      {label && <label className="block text-gray-700 mb-1">{label}</label>}
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring focus:border-blue-300"
      />
    </div>
  );
}

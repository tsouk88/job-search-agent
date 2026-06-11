import React, { useState, useEffect } from 'react';
import { Switch } from '@mui/material';

const DarkModeToggle = () => {
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const storedDarkMode = localStorage.getItem('darkMode');
    if (storedDarkMode) {
      setDarkMode(storedDarkMode === 'true');
    }
  }, []);

  const handleToggle = () => {
    setDarkMode(!darkMode);
    localStorage.setItem('darkMode', !darkMode);
  };

  return (
    <Switch
      checked={darkMode}
      onChange={handleToggle}
      name="darkMode"
      color="primary"
    />
  );
};

export default DarkModeToggle;
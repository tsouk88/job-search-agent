import React from 'react';
import { Skeleton } from '@mui/material';

const LoadingState = () => {
  return (
    <div className="flex flex-col p-4 border border-gray-200 rounded-lg">
      <Skeleton variant="text" width="100%" height={20} />
      <Skeleton variant="text" width="100%" height={20} />
      <Skeleton variant="text" width="100%" height={20} />
      <Skeleton variant="rectangular" width="100%" height={100} />
    </div>
  );
};

export default LoadingState;
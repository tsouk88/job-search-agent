import React from 'react';
import { Badge, Typography } from '@mui/material';

const JobCard = ({ job }) => {
  return (
    <div className="flex flex-col p-4 border border-gray-200 rounded-lg">
      <Typography variant="h6" className="font-bold mb-2">
        {job.title}
      </Typography>
      <Typography variant="body1" className="text-gray-600 mb-2">
        {job.company}
      </Typography>
      <div className="flex flex-wrap mb-2">
        {job.salary && (
          <Badge
            color="primary"
            badgeContent={job.salary}
            className="mr-2 mb-2"
          />
        )}
        {job.location && (
          <Badge
            color="primary"
            badgeContent={job.location}
            className="mr-2 mb-2"
          />
        )}
      </div>
      <Typography variant="body1" className="text-gray-600">
        {job.description}
      </Typography>
    </div>
  );
};

export default JobCard;
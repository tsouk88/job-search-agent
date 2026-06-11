import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { Grid, Container } from '@mui/material';
import JobCard from '../components/JobCard';
import LoadingState from '../components/LoadingState';

const Home = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchJobs = async () => {
      setLoading(true);
      const response = await fetch('/api/jobs');
      const data = await response.json();
      setJobs(data);
      setLoading(false);
    };
    fetchJobs();
  }, []);

  return (
    <div>
      <Head>
        <title>Job Search AI Agent</title>
      </Head>
      <Container maxWidth="lg" className="pt-4">
        <Grid container spacing={2}>
          {loading ? (
            <Grid item xs={12} sm={6} md={4} lg={3}>
              <LoadingState />
            </Grid>
          ) : (
            jobs.map((job) => (
              <Grid item xs={12} sm={6} md={4} lg={3} key={job.id}>
                <JobCard job={job} />
              </Grid>
            ))
          )}
        </Grid>
      </Container>
    </div>
  );
};

export default Home;
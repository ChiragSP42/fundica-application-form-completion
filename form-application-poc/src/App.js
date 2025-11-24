import React, { useState } from 'react';
import { uploadData } from 'aws-amplify/storage';
import './App.css';

function App() {
  const [username, setUsername] = useState('');
  const [applicationForm, setApplicationForm] = useState('job_application');
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [completedForm, setCompletedForm] = useState(null);
  const [error, setError] = useState('');
  const [executionStatus, setExecutionStatus] = useState('');

  const handleFileChange = (event) => {
    const selectedFiles = Array.from(event.target.files);
    if (selectedFiles.length > 10) {
      setError('Maximum 10 files allowed');
      return;
    }
    setFiles(selectedFiles);
    setError('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    
    if (!username.trim()) {
      setError('Username is required');
      return;
    }
    
    if (files.length === 0) {
      setError('Please upload at least one document');
      return;
    }

    setLoading(true);
    setError('');
    setExecutionStatus('Uploading documents...');

    try {
      // Step 1: Upload files to S3 with the specified path structure
      const normalizedUsername = username;
      const s3Path = `predictif-chiggi-testing/documents/${normalizedUsername}`;
      
      setExecutionStatus('Uploading documents to S3...');
      const uploadPromises = files.map(file =>
        uploadData({
          path: `${s3Path}/${file.name}`,
          data: file,
        }).result
      );

      await Promise.all(uploadPromises);
      console.log(`Successfully uploaded ${files.length} files to S3`);

      // Step 2: Call the API Gateway endpoint which triggers Step Functions
      setExecutionStatus('Initiating workflow...');
      const apiResponse = await fetch(
        process.env.REACT_APP_API_ENDPOINT,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            username: normalizedUsername,
            applicationForm: applicationForm,
            documentCount: files.length,
            s3Path: s3Path,
          }),
        }
      );

      if (!apiResponse.ok) {
        throw new Error(`API error: ${apiResponse.status}`);
      }

      const result = await apiResponse.json();
      console.log('Step Functions execution started:', result);

      setExecutionStatus('Processing documents and generating form...');

      // Step 3: Poll for execution status (for synchronous wait)
      // If using async, you can remove this and just show the execution ID
      if (result.executionArn) {
        // Poll for completion (you'll implement checkExecutionStatus in a separate function)
        const completedFormResult = await pollExecutionStatus(result.executionArn);
        setCompletedForm(completedFormResult);
        setExecutionStatus('');
      }

    } catch (err) {
      setError(`Error: ${err.message}`);
      setExecutionStatus('');
    } finally {
      setLoading(false);
    }
  };

  const pollExecutionStatus = async (executionArn) => {
    // Poll every 2 seconds for up to 5 minutes
    const maxAttempts = 150;
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const statusResponse = await fetch(
          `${process.env.REACT_APP_STATUS_ENDPOINT}?executionArn=${encodeURIComponent(executionArn)}`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );

        if (!statusResponse.ok) {
          throw new Error(`Status check failed: ${statusResponse.status}`);
        }

        const statusResult = await statusResponse.json();

        if (statusResult.status === 'SUCCEEDED') {
          return statusResult.output;
        } else if (statusResult.status === 'FAILED' || statusResult.status === 'TIMED_OUT' || statusResult.status === 'ABORTED') {
          throw new Error(`Execution ${statusResult.status}: ${statusResult.cause}`);
        }

        // Still running, wait 2 seconds and try again
        setExecutionStatus(`Processing... (${attempts}s)`);
        await new Promise(resolve => setTimeout(resolve, 2000));
        attempts++;
      } catch (err) {
        throw err;
      }
    }

    throw new Error('Execution timed out after 5 minutes');
  };

  return (
    <div className="container">
      <h1>Application Form Generator</h1>
      
      <form onSubmit={handleSubmit} className="form">
        <div className="form-group">
          <label htmlFor="username">Username:</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter your username"
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="applicationForm">Application Form Type:</label>
          <select
            id="applicationForm"
            value={applicationForm}
            onChange={(e) => setApplicationForm(e.target.value)}
            disabled={loading}
          >
            <option value="canexport_application_fomr">CanExport Application Form</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="documents">Upload Documents (up to 10):</label>
          <input
            id="documents"
            type="file"
            multiple
            onChange={handleFileChange}
            disabled={loading}
          />
          {files.length > 0 && <p>{files.length} file(s) selected</p>}
        </div>

        {error && <p className="error">{error}</p>}
        
        {executionStatus && <p className="status">{executionStatus}</p>}

        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Generate Application Form'}
        </button>
      </form>

      {completedForm && (
        <div className="completed-form">
          <h2>Completed Application Form</h2>
          <div className="form-content">
            {typeof completedForm === 'string' ? (
              <pre>{completedForm}</pre>
            ) : (
              <pre>{JSON.stringify(completedForm, null, 2)}</pre>
            )}
          </div>
          <button onClick={() => downloadForm(completedForm)}>
            Download Form
          </button>
        </div>
      )}
    </div>
  );
}

const downloadForm = (content) => {
  const element = document.createElement('a');
  const file = new Blob([typeof content === 'string' ? content : JSON.stringify(content, null, 2)], {
    type: 'text/plain',
  });
  element.href = URL.createObjectURL(file);
  element.download = 'completed_application_form.txt';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
};

export default App;

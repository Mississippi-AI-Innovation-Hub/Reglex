import axios, { AxiosError } from 'axios';
import type { Citation, ResearchFilters, ResponseMetadata, ApiResponse, VerificationResult } from '../types';

export interface ChatResponse {
  answer: string;
  citations?: Citation[];
  intent?: string;
  metadata?: ResponseMetadata;
  verification?: VerificationResult;
}

interface JobStartResponse {
  job_id: string;
  status: string;
  poll_url?: string;
}

interface JobStatusResponse {
  job_id: string;
  status: 'pending' | 'done' | 'failed';
  answer?: string;
  citations?: Citation[];
  intent?: string;
  metadata?: ResponseMetadata;
  error?: string;
}

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_DURATION_MS = 300000; // 5 minutes (backend can take ~3.5min for worst cases)

export class ChatService {
  private apiEndpoint: string;

  constructor(apiEndpoint: string) {
    this.apiEndpoint = apiEndpoint;
  }

  /**
   * Build the status poll URL from the chat endpoint.
   * e.g. /prod/v2/query → /prod/v2/query/status/{job_id}
   */
  private buildStatusUrl(jobId: string): string {
    return `${this.apiEndpoint.replace(/\/$/, '')}/status/${jobId}`;
  }

  async sendMessage(
    message: string,
    options?: {
      filters?: ResearchFilters;
      history?: { role: string; content: string }[];
      mode?: 'research' | 'chat' | 'compare' | 'count';
      model?: string;
      onStatusUpdate?: (status: string) => void;
    }
  ): Promise<ChatResponse> {
    const sanitizedMessage = message.trim();
    if (!sanitizedMessage) throw new Error('Message cannot be empty');

    const requestBody: Record<string, unknown> = { query: sanitizedMessage };
    if (options?.filters) requestBody.filters = options.filters;
    if (options?.history) requestBody.history = options.history;
    if (options?.mode) requestBody.mode = options.mode;
    if (options?.model) requestBody.model = options.model;

    try {
      // Step 1: POST to create an async job (returns 202 + job_id)
      const startResp = await axios.post<JobStartResponse | ApiResponse>(
        this.apiEndpoint,
        requestBody,
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 30000,
          // Accept 202 as a successful response
          validateStatus: (s) => s >= 200 && s < 300,
        },
      );

      const startData = startResp.data as JobStartResponse & ApiResponse;

      // Backward compat: if server returned a complete answer synchronously, use it
      if (startData.answer) {
        return {
          answer: startData.answer,
          citations: startData.citations || [],
          intent: startData.intent,
          metadata: startData.metadata,
        };
      }

      const jobId = startData.job_id;
      if (!jobId) {
        throw new Error('Server did not return a job_id');
      }

      // Step 2: Poll status endpoint until done or timeout
      const start = Date.now();
      while (Date.now() - start < MAX_POLL_DURATION_MS) {
        const elapsed = Math.round((Date.now() - start) / 1000);
        options?.onStatusUpdate?.(`pending (${elapsed}s)`);

        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

        const statusResp = await axios.get<JobStatusResponse>(
          this.buildStatusUrl(jobId),
          { timeout: 10000 },
        );
        const job = statusResp.data;

        if (job.status === 'done') {
          return {
            answer: job.answer || '',
            citations: job.citations || [],
            intent: job.intent,
            metadata: job.metadata,
          };
        }
        if (job.status === 'failed') {
          throw new Error(job.error || 'Job failed');
        }
        // else: still pending — continue polling
      }

      throw new Error('Query timed out after 5 minutes');
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<ApiResponse>;
        if (axiosError.response) {
          const errorMessage = axiosError.response.data?.error ||
                              axiosError.response.data?.message ||
                              `Server error: ${axiosError.response.status}`;
          throw new Error(errorMessage);
        } else if (axiosError.request) {
          throw new Error('No response from server. Check console for details.');
        }
      }
      if (error instanceof Error) throw error;
      throw new Error('An unexpected error occurred');
    }
  }

  isConfigured(): boolean {
    return Boolean(this.apiEndpoint);
  }
}

export const createChatService = (apiEndpoint: string): ChatService => {
  return new ChatService(apiEndpoint);
};

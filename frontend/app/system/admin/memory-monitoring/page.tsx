import { MemoryMonitoringClient } from './components/memory-monitoring-client';

/**
 * Memory Monitoring Page (Server Component)
 *
 * Displays memory system metrics including:
 * - Retrieval trigger rate
 * - Hit rate
 * - Additional latency
 * - Session backlog
 */
export default function MemoryMonitoringPage() {
  return (
    <div className="space-y-8 max-w-7xl">
      <MemoryMonitoringClient />
    </div>
  );
}

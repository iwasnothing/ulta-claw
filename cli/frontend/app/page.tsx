'use client'

import { useEffect, useState } from 'react'
import useSWR from 'swr'

// Types
type ComponentStatus = 'healthy' | 'degraded' | 'unhealthy'

interface HealthCheckResult {
  status: ComponentStatus
  message: string
  response_time_ms: number
  details?: Record<string, unknown>
}

interface HealthData {
  status: ComponentStatus
  timestamp: string
  checks: Record<string, HealthCheckResult>
}

interface Skill {
  name: string
  description: string
  condition: string
  instructions: string
  resources: string
}

interface SkillCatalog {
  [name: string]: {
    name: string
    description: string
    condition: string
  }
}

interface HealthCardProps {
  name: string
  result: HealthCheckResult
}

// Component icons
const ComponentIcons: Record<string, string> = {
  gateway: '🌐',
  adaptor_channel: '🔄',
  agent: '🤖',
  redis: '💾',
  litellm: '⚡',
  squid: '🦑',
  connections: '🔗',
}

// Status colors
const statusColors: Record<ComponentStatus, string> = {
  healthy: 'bg-green-500',
  degraded: 'bg-yellow-500',
  unhealthy: 'bg-red-500',
}

const statusTextColors: Record<ComponentStatus, string> = {
  healthy: 'text-green-600',
  degraded: 'text-yellow-600',
  unhealthy: 'text-red-600',
}

const statusBgColors: Record<ComponentStatus, string> = {
  healthy: 'bg-green-50',
  degraded: 'bg-yellow-50',
  unhealthy: 'bg-red-50',
}

const statusBorderColors: Record<ComponentStatus, string> = {
  healthy: 'border-green-200',
  degraded: 'border-yellow-200',
  unhealthy: 'border-red-200',
}

// Fetcher for SWR
const fetcher = async (url: string) => {
  const res = await fetch(url, {
    cache: 'no-store',
  })
  if (!res.ok) {
    throw new Error('Failed to fetch data')
  }
  return res.json()
}

// Health Card Component
function HealthCard({ name, result }: HealthCardProps) {
  const displayName = name
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

  return (
    <div
      className={`border rounded-lg p-4 transition-all hover:shadow-lg ${statusBgColors[result.status]} ${statusBorderColors[result.status]}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{ComponentIcons[name] || '📊'}</span>
          <h3 className="font-semibold text-gray-900">{displayName}</h3>
        </div>
        <div className={`px-2 py-1 rounded-full text-xs font-bold ${statusTextColors[result.status]} ${statusBgColors[result.status]}`}>
          {result.status.toUpperCase()}
        </div>
      </div>
      <p className="text-sm text-gray-600 mb-2">{result.message}</p>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span>{result.response_time_ms.toFixed(1)} ms</span>
      </div>
    </div>
  )
}

// Detail Row Component
function DetailRow({ label, value }: { label: string; value: string | number | null }) {
  if (value === null || value === undefined) return null
  return (
    <div className="flex justify-between text-sm py-1 border-b border-gray-100 last:border-0">
      <span className="text-gray-600">{label}</span>
      <span className="text-gray-900 font-medium">{String(value)}</span>
    </div>
  )
}

// Detail Modal Component
function DetailModal({
  isOpen,
  onClose,
  componentName,
  result,
}: {
  isOpen: boolean
  onClose: () => void
  componentName: string
  result: HealthCheckResult
}) {
  if (!isOpen) return null

  const displayName = componentName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full m-4 max-h-[80vh] overflow-auto">
        <div className="p-4 border-b flex items-center justify-between">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <span className="text-2xl">{ComponentIcons[componentName] || '📊'}</span>
            {displayName}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>
        <div className="p-4">
          <div className={`mb-4 p-3 rounded ${statusBgColors[result.status]}`}>
            <div className={`font-bold ${statusTextColors[result.status]} mb-1`}>
              {result.status.toUpperCase()}
            </div>
            <div className="text-sm text-gray-700">{result.message}</div>
            <div className="text-xs text-gray-500 mt-1">
              Response time: {result.response_time_ms.toFixed(1)} ms
            </div>
          </div>

          {result.details && Object.keys(result.details).length > 0 && (
            <div>
              <h4 className="font-semibold text-sm text-gray-900 mb-2">Details</h4>
              <div className="space-y-0">
                {Object.entries(result.details).map(([key, value]) => {
                  if (key === 'connections') {
                    const connections = value as Record<string, { healthy: boolean; latency_ms?: number }>
                    return (
                      <div key={key} className="mt-2">
                        <div className="text-sm text-gray-600 mb-1">Connections</div>
                        <div className="pl-2 space-y-1">
                          {Object.entries(connections).map(([connName, connData]) => (
                            <div key={connName} className="flex items-center justify-between text-xs py-1">
                              <div className="flex items-center gap-1">
                                <span className={connData.healthy ? 'text-green-600' : 'text-red-600'}>
                                  {connData.healthy ? '✓' : '✗'}
                                </span>
                                <span className="text-gray-700">{connName}</span>
                              </div>
                              <span className="text-gray-500">
                                {connData.latency_ms ? `${connData.latency_ms.toFixed(2)}ms` : 'failed'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  }
                  return (
                    <DetailRow
                      key={key}
                      label={key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      value={
                        typeof value === 'object'
                          ? JSON.stringify(value)
                          : value as string | number | null
                      }
                    />
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Skill Card Component
function SkillCard({ skill, onDelete }: { skill: SkillCatalog[string]; onDelete: (name: string) => void }) {
  return (
    <div className="border rounded-lg p-4 bg-white hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-gray-900">{skill.name}</h3>
        <button
          onClick={() => onDelete(skill.name)}
          className="text-red-500 hover:text-red-700 text-sm"
          title="Delete skill"
        >
          🗑️
        </button>
      </div>
      <p className="text-sm text-gray-600 mb-2">{skill.description}</p>
      <div className="text-xs text-gray-500">
        <strong>When to use:</strong> {skill.condition}
      </div>
    </div>
  )
}

// Create Skill Modal Component
function CreateSkillModal({
  isOpen,
  onClose,
  onCreate,
}: {
  isOpen: boolean
  onClose: () => void
  onCreate: (skill: Omit<Skill, 'name'> & { name: string }) => void
}) {
  if (!isOpen) return null

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [condition, setCondition] = useState('')
  const [instructions, setInstructions] = useState('')
  const [resources, setResources] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validation
    if (!name || !description || !condition || !instructions) {
      setError('Please fill in all required fields')
      return
    }

    setIsCreating(true)
    try {
      await onCreate({ name, description, condition, instructions, resources })
      onClose()
      // Reset form
      setName('')
      setDescription('')
      setCondition('')
      setInstructions('')
      setResources('')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create skill')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full m-4 max-h-[90vh] overflow-auto">
        <div className="p-4 border-b flex items-center justify-between">
          <h3 className="text-lg font-semibold">Create New Skill</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
          >
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Skill Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., web_search"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., Search the web for information"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Condition to Use <span className="text-red-500">*</span>
            </label>
            <textarea
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={2}
              placeholder="e.g., When the user asks for recent information, facts, or needs to search the internet"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Instructions <span className="text-red-500">*</span>
            </label>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={6}
              placeholder="Step-by-step instructions for executing this skill..."
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Additional Resources (Optional)
            </label>
            <textarea
              value={resources}
              onChange={(e) => setResources(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={3}
              placeholder="Example input/output, supporting files, etc."
            />
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCreating ? 'Creating...' : 'Create Skill'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Main Page Component
export default function Home() {
  const [selectedComponent, setSelectedComponent] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [showSkills, setShowSkills] = useState(false)
  const [showCreateSkill, setShowCreateSkill] = useState(false)
  const [skills, setSkills] = useState<SkillCatalog>({})
  const [skillsLoading, setSkillsLoading] = useState(false)

  const { data, error, isLoading } = useSWR<HealthData>(
    '/api/health',
    fetcher,
    {
      refreshInterval: autoRefresh ? 3000 : 0,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
    }
  )

  // Load skills when showing skills tab
  useEffect(() => {
    if (showSkills) {
      loadSkills()
    }
  }, [showSkills])

  const loadSkills = async () => {
    setSkillsLoading(true)
    try {
      const res = await fetch('/api/skills/catalog')
      if (res.ok) {
        const data = await res.json()
        setSkills(data.catalog || {})
      }
    } catch (err) {
      console.error('Failed to load skills:', err)
    } finally {
      setSkillsLoading(false)
    }
  }

  const handleCreateSkill = async (skill: Omit<Skill, 'name'> & { name: string }) => {
    const res = await fetch('/api/skills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(skill),
    })

    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to create skill')
    }

    await loadSkills()
  }

  const handleDeleteSkill = async (name: string) => {
    if (!confirm(`Are you sure you want to delete skill "${name}"?`)) {
      return
    }

    const res = await fetch(`/api/skills/${name}`, {
      method: 'DELETE',
    })

    if (res.ok) {
      await loadSkills()
    }
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">❌</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Error Loading Data</h1>
          <p className="text-gray-600">Failed to fetch health check data</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin text-6xl mb-4">⏳</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Loading...</h1>
          <p className="text-gray-600">Fetching health check data</p>
        </div>
      </div>
    )
  }

  const overallStatus = data.status

  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between flex-wrap gap-4 mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                Secure Agent Dashboard
              </h1>
              <p className="text-gray-600">
                {showSkills ? 'Manage agent skills' : 'Real-time monitoring of system components'}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  autoRefresh
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {autoRefresh ? '🔄 Auto-refreshing' : '⏸️ Paused'}
              </button>
              {!autoRefresh && showSkills && (
                <button
                  onClick={loadSkills}
                  disabled={skillsLoading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {skillsLoading ? 'Loading...' : '🔄 Refresh'}
                </button>
              )}
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setShowSkills(false)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                !showSkills
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              📊 Health
            </button>
            <button
              onClick={() => setShowSkills(true)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                showSkills
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              🎯 Skills
            </button>
          </div>

          {/* Overall Status Badge */}
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg ${statusBgColors[overallStatus]} ${statusBorderColors[overallStatus]}`}>
            <div className={`w-3 h-3 rounded-full ${statusColors[overallStatus]} animate-pulse`} />
            <span className={`font-bold ${statusTextColors[overallStatus]}`}>
              System Status: {overallStatus.toUpperCase()}
            </span>
            <span className="text-sm text-gray-500">
              Last updated: {new Date(data.timestamp).toLocaleTimeString()}
            </span>
          </div>
        </div>

        {/* Health Check Section */}
        {!showSkills && (
          <div>
            {/* Health Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
              {Object.entries(data.checks).map(([name, result]) => (
                <div
                  key={name}
                  className="cursor-pointer"
                  onClick={() => setSelectedComponent(name)}
                >
                  <HealthCard name={name} result={result} />
                </div>
              ))}
            </div>

            {/* Last Updated Info */}
            <div className="text-center text-sm text-gray-500">
              <p>
                {autoRefresh ? 'Auto-refreshing every 3 seconds' : 'Refresh paused'} •
                Click on any component to view details
              </p>
            </div>
          </div>
        )}

        {/* Skills Section */}
        {showSkills && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                Agent Skills ({Object.keys(skills).length})
              </h2>
              <button
                onClick={() => setShowCreateSkill(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
              >
                + Create Skill
              </button>
            </div>

            {skillsLoading && Object.keys(skills).length === 0 ? (
              <div className="text-center py-12 text-gray-500">Loading skills...</div>
            ) : Object.keys(skills).length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <div className="text-6xl mb-4">🎯</div>
                <p className="text-lg mb-2">No skills configured yet</p>
                <p className="text-sm">Click "Create Skill" to add your first skill</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.values(skills).map((skill) => (
                  <SkillCard
                    key={skill.name}
                    skill={skill}
                    onDelete={handleDeleteSkill}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedComponent && (
        <DetailModal
          isOpen={!!selectedComponent}
          onClose={() => setSelectedComponent(null)}
          componentName={selectedComponent}
          result={data.checks[selectedComponent]}
        />
      )}

      {/* Create Skill Modal */}
      <CreateSkillModal
        isOpen={showCreateSkill}
        onClose={() => setShowCreateSkill(false)}
        onCreate={handleCreateSkill}
      />
    </main>
  )
}

/**
 * API route for health checks.
 * Note: This route is not used - the frontend directly calls the FastAPI backend.
 * This file is kept for future extension if needed.
 */

import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8888'
    const response = await fetch(`${API_URL}/api/health`, {
      cache: 'no-store',
    })

    if (!response.ok) {
      throw new Error(`FastAPI returned ${response.status}`)
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Error proxying health request:', error)
    return NextResponse.json(
      { error: 'Failed to fetch health data', details: String(error) },
      { status: 500 }
    )
  }
}

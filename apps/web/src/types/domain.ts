export type Resume = {
  id: string
  source_type: 'text' | 'upload'
  original_filename: string | null
  media_type: string | null
  file_size: number | null
  original_text: string
  extracted_text: string
  structured_data: {
    name?: string | null
    skills?: string[]
    bullets?: string[]
    sections?: Array<{ kind: string; heading: string | null; content: string }>
  }
  extraction_warnings: string[]
  confirmed: boolean
  created_at: string
  updated_at: string
}

export type Requirement = {
  id: string
  category: string
  text: string
  normalized_key: string | null
  priority: 'required' | 'preferred' | 'context'
  explicitness: 'explicit' | 'inferred' | 'ambiguous'
  source_excerpt: string
}

export type JobDescription = {
  id: string
  raw_text: string
  title: string | null
  employer: string | null
  location: string | null
  structured_data: Record<string, unknown>
  requirements: Requirement[]
  created_at: string
  updated_at: string
}

export type Score = {
  id: string
  category: string
  score: number
  maximum: number
  reason: string
  improvements: string[]
}

export type Evidence = {
  id: string
  requirement_id: string | null
  requirement: string
  status: 'supported' | 'not_found' | 'transferable' | 'ambiguous'
  resume_excerpt: string | null
  source_section: string | null
  confidence: 'high' | 'medium' | 'low'
  interpretation: string | null
}

export type Recommendation = {
  id: string
  priority: 'Critical' | 'High impact' | 'Moderate impact' | 'Optional polish'
  title: string
  explanation: string
  supporting_evidence: string | null
  role_reason: string
  recommended_action: string
  confidence: string
  confirmation_required: boolean
  source: 'deterministic' | 'model'
  status: 'open' | 'accepted' | 'dismissed'
}

export type InterviewQuestion = {
  id: string
  category: 'technical' | 'behavioral' | 'experience_gap'
  question: string
  talking_points: string[]
  resume_evidence: string | null
  confidence: string
  source: 'deterministic' | 'model'
}

export type AnalysisSummary = {
  id: string
  name: string
  state: 'draft' | 'ready' | 'analyzing' | 'completed' | 'failed'
  overall_score: number | null
  model_status: string
  created_at: string
  updated_at: string
  target_job_title: string | null
  target_employer: string | null
}

export type Analysis = AnalysisSummary & {
  resume_id: string
  job_description_id: string
  deterministic_complete: boolean
  result: {
    top_strengths?: string[]
    top_gaps?: string[]
    transferable_experience?: string[]
    disclaimer?: string
    model_executive_summary?: string
    model_responsibility_alignment?: number
    model_transferable_experience?: string[]
    model_limitations?: string[]
    model_generated?: boolean
    analysis_confidence?: 'high' | 'medium' | 'low'
    bullet_analysis?: Array<{
      original_bullet: string
      action_verb: string | null
      action_led: boolean
      task_clarity: 'high' | 'medium' | 'low'
      technical_detail: string[]
      business_impact: boolean
      measurable_outcome: boolean
      job_relevance: number
      length_words: number
      redundant_phrases: string[]
      unsupported_claims: string[]
      verification_note: string
    }>
  }
  error_message: string | null
  scores: Score[]
  evidence: Evidence[]
  recommendations: Recommendation[]
  interview_questions: InterviewQuestion[]
}

export type BulletRewrite = {
  original_bullet: string
  suggested_bullet: string
  reason: string
  factual_sources: string[]
  confirmation_required: boolean
  model_generated: boolean
  warning: string
}

export type AppSettings = {
  provider: 'local_first' | 'ollama' | 'openai_compatible' | 'disabled'
  local_model: string
  local_provider_url: string
  remote_model: string
  remote_provider_url: string
  openai_reasoning_effort: 'none' | 'low' | 'medium' | 'high'
  ollama_context_tokens: number
  remote_api_key_configured: boolean
  remote_fallback_configured: boolean
  model: string
  provider_url: string
  model_temperature: number
  model_max_tokens: number
  model_timeout_seconds: number
  model_retries: number
  max_upload_bytes: number
  data_dir: string
  remote_provider_warning: boolean
}

export type Health = {
  status: string
  database: string
  provider: string
  deterministic_analysis: string
  ai_features: string
  active_provider: string | null
  provider_checks: Array<{
    provider: string
    model: string
    status: 'available' | 'unavailable' | 'not_configured'
    local: boolean
  }>
  remote_fallback_configured: boolean
}

"use client"

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot,
  Code2,
  Terminal,
  FileText,
  TestTube,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ChevronRight
} from 'lucide-react'

import { AgentLog, AgentPersona, ToolCall } from '@/types/schema'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

// Persona Mapping
const personaConfig: Record<AgentPersona, { icon: React.ReactNode; label: string; color: string }> = {
  planner: { icon: <Bot className="h-4 w-4" />, label: 'Planner', color: 'text-indigo-400' },
  coder_be: { icon: <Code2 className="h-4 w-4" />, label: 'Backend', color: 'text-emerald-400' },
  coder_fe: { icon: <Code2 className="h-4 w-4" />, label: 'Frontend', color: 'text-cyan-400' },
  coder_infra: { icon: <Terminal className="h-4 w-4" />, label: 'Infra', color: 'text-orange-400' },
  qa: { icon: <TestTube className="h-4 w-4" />, label: 'QA', color: 'text-rose-400' },
  docs: { icon: <FileText className="h-4 w-4" />, label: 'Docs', color: 'text-slate-400' },
}

interface AgentCardProps {
  log: AgentLog
  isLatest?: boolean
}

export function AgentCard({ log, isLatest = false }: AgentCardProps) {
  const persona = personaConfig[log.agent_persona as AgentPersona] || personaConfig.planner

  // Visual state determination
  let borderColor = "border-border"
  let glowEffect = ""

  // High confidence = Success
  if (log.confidence_score >= 0.8) {
    borderColor = "border-emerald-500/50"
    if (isLatest) glowEffect = "shadow-[0_0_15px_rgba(16,185,129,0.15)]"
  }
  // Low confidence/Review = Warning
  else if (log.requires_review) {
    borderColor = "border-rose-500/50"
    if (isLatest) glowEffect = "shadow-[0_0_15px_rgba(244,63,94,0.15)]"
  }
  // Thinking (Latest & not complete) - handled by parent logic usually, but here based on latest
  else if (isLatest) {
    borderColor = "border-indigo-500/50"
    glowEffect = "shadow-[0_0_15px_rgba(99,102,241,0.15)]"
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="mb-4"
    >
      <Card
        role="article"
        aria-label={`Agent action: ${log.ui_title}`}
        className={cn(
          "bg-card/50 backdrop-blur-sm border transition-all duration-300",
          borderColor,
          glowEffect
        )}>
        <div className="p-4">
          {/* Header Row */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className={cn("gap-1 bg-background/50", persona.color)}>
                {persona.icon}
                <span>{persona.label}</span>
              </Badge>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {new Date(log.created_at).toLocaleTimeString('en-GB', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: false
                })}
              </span>
            </div>

            <Badge
              variant={log.confidence_score >= 0.8 ? "success" : log.requires_review ? "destructive" : "secondary"}
              className="text-xs"
            >
              {Math.round(log.confidence_score * 100)}% Confidence
            </Badge>
          </div>

          {/* Title & Subtitle */}
          <div className="mb-3 space-y-1">
            <h3 className="text-base font-semibold leading-none tracking-tight text-foreground/90">
              {log.ui_title}
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {log.ui_subtitle}
            </p>
          </div>

          {/* Tool Calls Summary (Mini-badges) */}
          {log.tool_calls && log.tool_calls.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {(log.tool_calls as unknown as ToolCall[]).map((tool: ToolCall) => (
                <Badge key={tool.id} variant="secondary" className="text-[10px] h-5 px-1.5 font-mono text-muted-foreground">
                  <Terminal className="h-3 w-3 mr-1" />
                  {tool.tool_name}
                </Badge>
              ))}
            </div>
          )}

          {/* Technical Details Accordion */}
          {(log.technical_reasoning || (log.tool_calls && log.tool_calls.length > 0)) && (
            <Accordion type="single" collapsible className="w-full">
              <AccordionItem value="details" className="border-b-0">
                <AccordionTrigger className="py-0 text-xs text-muted-foreground hover:text-primary hover:no-underline data-[state=open]:text-primary">
                  <span>View Technical Details</span>
                </AccordionTrigger>
                <AccordionContent className="pt-3 pb-0">
                  <div className="rounded-md bg-muted/50 p-3 font-mono text-xs text-muted-foreground overflow-x-auto">
                    {log.technical_reasoning && (
                      <div className="mb-3">
                        <div className="font-semibold mb-1 text-foreground/70">Reasoning:</div>
                        <div className="whitespace-pre-wrap">{log.technical_reasoning}</div>
                      </div>
                    )}

                    {log.tool_calls && log.tool_calls.length > 0 && (
                      <div>
                        <div className="font-semibold mb-1 text-foreground/70">Tool Calls:</div>
                        <div className="space-y-2">
                          {(log.tool_calls as unknown as ToolCall[]).map((tool: ToolCall, i) => (
                            <div key={tool.id} className="border-l-2 border-border pl-2">
                              <div className="text-primary">{tool.tool_name}</div>
                              <pre className="mt-1 text-[10px]">{JSON.stringify(tool.arguments, null, 2)}</pre>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )}
        </div>
      </Card>
    </motion.div>
  )
}

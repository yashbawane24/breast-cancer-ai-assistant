import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingDown, TrendingUp, AlertTriangle, Loader2, Sparkles, ChevronDown, Filter, FileText } from 'lucide-react'
import Card from '../components/common/Card.jsx'
import TrendChart from '../components/trends/TrendChart.jsx'
import ComparisonChart from '../components/trends/ComparisonChart.jsx'
import ClinicalAlertsCard from '../components/trends/ClinicalAlertsCard.jsx'
import { getTimeline, getReports, compareReports, getClinicalAlerts } from '../services/api.js'
import Translate from '../components/common/Translate.jsx'
import { useLanguage } from '../context/LanguageContext.jsx'
import { useTrends } from '../context/TrendsContext.jsx'

export default function TrendsPage() {
  const navigate = useNavigate()
  const {
    marker, setMarker,
    docTypeFilter, setDocTypeFilter,
    timelineData, setTimelineData,
    reports, setReports,
    selectedReport1, setSelectedReport1,
    selectedReport2, setSelectedReport2,
    comparisonData, setComparisonData,
    loadingTimeline, setLoadingTimeline,
    loadingCompare, setLoadingCompare,
    initialized, setInitialized
  } = useTrends()

  const [alerts, setAlerts] = useState([])
  const { lang, t } = useLanguage()

  useEffect(() => {
    if (!initialized) {
      getReports().then(res => {
        const raw = res.data || []
        const sorted = [...raw].sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date))
        setReports(sorted)
        setInitialized(true)
      }).catch(err => {
        console.error("Could not fetch reports", err)
        setReports([])
        setInitialized(true)
      })
    }

    getClinicalAlerts().then(res => {
      setAlerts(res || [])
    }).catch(() => setAlerts([]))
  }, [initialized, setReports, setInitialized])

  const uniqueDocTypes = useMemo(() => {
    const types = new Set()
    reports.forEach(r => types.add(r.document_type))
    return Array.from(types)
  }, [reports])

  const filteredReports = useMemo(() => {
    if (docTypeFilter === 'all') return reports;
    const filtered = reports.filter(r => r.document_type === docTypeFilter)
    return filtered.length > 0 ? filtered : reports
  }, [reports, docTypeFilter])

  useEffect(() => {
    if (filteredReports.length >= 2) {
      setSelectedReport1(filteredReports[1].id)
      setSelectedReport2(filteredReports[0].id)
    } else if (filteredReports.length === 1) {
      setSelectedReport1(filteredReports[0].id)
      setSelectedReport2(filteredReports[0].id)
    } else {
      setSelectedReport1('')
      setSelectedReport2('')
    }
  }, [filteredReports, setSelectedReport1, setSelectedReport2])

  const uniqueMarkers = useMemo(() => {
    const markers = new Set(['Hemoglobin', 'CA 15-3'])
    filteredReports.forEach(r => {
      r.extracted_entities?.lab_parameters?.forEach(p => {
        if (p.name) markers.add(p.name)
      })
    })
    return Array.from(markers).sort()
  }, [filteredReports])

  useEffect(() => {
    if (!uniqueMarkers.includes(marker)) {
      setMarker(uniqueMarkers[0])
    }
  }, [uniqueMarkers, marker, setMarker])

  useEffect(() => {
    if (!marker) return
    setLoadingTimeline(true)
    getTimeline(marker, docTypeFilter).then(res => {
      const rawData = res.data || []
      const formatted = rawData.map((item, i) => ({
        visit: `V${i+1}`,
        label: item.date ? new Date(item.date).toLocaleDateString() : `V${i+1}`,
        value: item.value
      }))
      setTimelineData(formatted)
      setLoadingTimeline(false)
    }).catch(err => {
      console.error(err)
      setTimelineData([])
      setLoadingTimeline(false)
    })
  }, [marker, docTypeFilter, setLoadingTimeline, setTimelineData])

  const handleCompare = () => {
    if (!selectedReport1 || !selectedReport2) return;
    setLoadingCompare(true)
    setComparisonData(null)
    compareReports(selectedReport1, selectedReport2, lang).then(res => {
      setComparisonData(res.data)
      setLoadingCompare(false)
    }).catch(err => {
      console.error(err)
      setComparisonData(null)
      setLoadingCompare(false)
    })
  }

  if (initialized && reports.length === 0) {
    return (
      <div className="mx-auto max-w-[1600px] px-6 sm:px-8 lg:px-12 py-16 space-y-8">
        <div>
          <p className="text-sm font-medium uppercase tracking-widest text-rose-600"><Translate>Health trends</Translate></p>
          <h1 className="mt-2 font-display text-3xl text-ink"><Translate>Your timeline, compared</Translate></h1>
          <p className="mt-2 text-ink-soft max-w-xl">
            <Translate>Track longitudinal biomarker trajectories, lab parameters, and multi-visit shifts over time.</Translate>
          </p>
        </div>

        <div className="text-center py-20 border border-ink/5 rounded-2xl bg-white shadow-sm">
          <FileText size={48} className="mx-auto text-ink/20 mb-4" />
          <h3 className="text-lg font-medium text-ink"><Translate>No reports uploaded yet</Translate></h3>
          <p className="text-ink-soft mt-1 mb-6 max-w-md mx-auto">
            <Translate>Upload at least one medical report or blood test to visualize your biomarker timelines and compare visit findings.</Translate>
          </p>
          <button 
            onClick={() => navigate('/upload')} 
            className="bg-rose-500 text-white px-6 py-2.5 rounded-full font-medium text-sm hover:bg-rose-600 transition shadow-sm inline-flex items-center gap-2"
          >
            <Translate>Upload your first report</Translate>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1600px] px-6 sm:px-8 lg:px-12 py-12 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-widest text-rose-600"><Translate>Health trends</Translate></p>
          <h1 className="mt-2 font-display text-3xl text-ink"><Translate>Your timeline, compared</Translate></h1>
        </div>
        
        <div className="relative inline-block">
          <Filter size={14} className="absolute left-3 top-3.5 text-ink-soft pointer-events-none" />
          <select 
            value={docTypeFilter}
            onChange={(e) => setDocTypeFilter(e.target.value)}
            className="appearance-none font-display text-sm font-medium text-ink bg-transparent border border-ink/10 hover:border-ink/20 rounded-lg focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 pl-9 pr-8 py-2 shadow-sm transition cursor-pointer"
          >
            <option value="all" className="font-sans text-sm">{t('All Documents')}</option>
            {uniqueDocTypes.map(t => (
              <option key={t} value={t} className="font-sans text-sm">{t.replace('_', ' ')}</option>
            ))}
          </select>
          <ChevronDown size={16} className="absolute right-3 top-3 text-ink-soft pointer-events-none" />
        </div>
      </div>

      {/* Feature 2: Proactive Clinical Alerts Banner */}
      {alerts && alerts.length > 0 && <ClinicalAlertsCard alerts={alerts} />}

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="md:col-span-2">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-soft mb-1"><Translate>Biomarker Timeline</Translate></p>
              <div className="relative inline-block mt-2">
                <select 
                  value={marker} 
                  onChange={(e) => setMarker(e.target.value)}
                  className="appearance-none font-display text-sm font-medium text-ink bg-transparent border border-ink/10 hover:border-ink/20 rounded-lg focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 w-64 px-4 py-2 cursor-pointer shadow-sm transition"
                >
                  {uniqueMarkers.map(m => (
                    <option key={m} value={m} className="font-sans text-sm">{m}</option>
                  ))}
                </select>
                <ChevronDown size={16} className="absolute right-3 top-3 text-ink-soft pointer-events-none" />
              </div>
            </div>
          </div>

          <div className="mt-6">
            {loadingTimeline ? (
              <div className="flex justify-center items-center h-48">
                <Loader2 className="animate-spin text-rose-500" size={24} />
              </div>
            ) : (
              <TrendChart data={timelineData} marker={marker} />
            )}
          </div>
        </Card>

        {/* Compare 2 Reports */}
        <Card className="md:col-span-2">
          <p className="mb-4 text-xs font-medium uppercase tracking-wide text-ink-soft">
            <Translate>Compare two reports</Translate>
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <select
              value={selectedReport1}
              onChange={(e) => setSelectedReport1(e.target.value)}
              className="focus-ring rounded-xl border border-ink/10 bg-porcelain px-4 py-2.5 text-sm text-ink flex-1 min-w-[200px]"
            >
              <option value="">{t('Select baseline report...')}</option>
              {filteredReports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.extracted_entities?.report_date || new Date(r.upload_date).toLocaleDateString()} — {r.document_type.replace('_', ' ')}
                </option>
              ))}
            </select>
            <span className="text-sm font-medium text-ink-soft"><Translate>vs</Translate></span>
            <select
              value={selectedReport2}
              onChange={(e) => setSelectedReport2(e.target.value)}
              className="focus-ring rounded-xl border border-ink/10 bg-porcelain px-4 py-2.5 text-sm text-ink flex-1 min-w-[200px]"
            >
              <option value="">{t('Select recent report...')}</option>
              {filteredReports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.extracted_entities?.report_date || new Date(r.upload_date).toLocaleDateString()} — {r.document_type.replace('_', ' ')}
                </option>
              ))}
            </select>
            <button
              onClick={handleCompare}
              disabled={!selectedReport1 || !selectedReport2 || loadingCompare}
              className="focus-ring rounded-xl bg-ink px-5 py-2.5 text-sm font-medium text-white transition hover:bg-ink-light disabled:opacity-50"
            >
              {loadingCompare ? <Loader2 size={16} className="animate-spin" /> : <Translate>Compare</Translate>}
            </button>
          </div>

          {comparisonData && (
            <div className="mt-6 pt-6 border-t border-ink/5 space-y-4">
              <div className="p-4 bg-rose-50/60 rounded-xl border border-rose-100 flex items-start gap-3">
                <Sparkles className="text-rose-600 mt-0.5 shrink-0" size={18} />
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-rose-950 text-sm"><Translate>AI Longitudinal Insights</Translate></p>
                    {comparisonData.confidence_score !== undefined && comparisonData.confidence_score !== null && (
                      <span className="text-[11px] font-medium text-rose-600 bg-rose-100 px-2 py-0.5 rounded-full">
                        {comparisonData.confidence_score}% <Translate>confidence</Translate>
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-rose-900/90 mt-1">{comparisonData.summary}</p>
                </div>
              </div>

              {comparisonData.chart_data && comparisonData.chart_data.length > 0 ? (
                <ComparisonChart 
                  chartData={comparisonData.chart_data} 
                  insights={comparisonData.insights || []} 
                />
              ) : (
                <div className="p-4 bg-porcelain/60 rounded-xl text-center text-xs text-ink-soft border border-ink/5">
                  <Translate>No common numerical lab parameters were found between these two reports to generate a percent-change bar chart.</Translate>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

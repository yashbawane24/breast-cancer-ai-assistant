import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FileText, Ruler, ListTree, Sparkles, AlertCircle, Loader2, Pill, Stethoscope, CheckCircle2 } from 'lucide-react'
import Card from '../components/common/Card.jsx'
import Badge from '../components/common/Badge.jsx'
import MTSTriageCard from '../components/report/MTSTriageCard.jsx'
import ClinicalAlertsCard from '../components/trends/ClinicalAlertsCard.jsx'
import { getReport, getTriageAssessment, getClinicalAlerts } from '../services/api.js'
import Translate from '../components/common/Translate.jsx'

export default function ReportInsightsPage() {
  const [searchParams] = useSearchParams()
  const reportId = searchParams.get('id')
  const [report, setReport] = useState(null)
  const [triage, setTriage] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let interval;
    const fetchReport = async () => {
      try {
        let currentId = reportId;
        if (!currentId) {
          const { getReports } = await import('../services/api.js');
          const allRes = await getReports();
          if (allRes.data && allRes.data.length > 0) {
            currentId = allRes.data[0].id;
            window.history.replaceState({}, '', `/report?id=${currentId}`);
          } else {
            setError("No reports uploaded yet.");
            setLoading(false);
            return;
          }
        }

        const res = await getReport(currentId)
        const data = res.data
        if (data.status === 'processing') {
          return;
        }
        setReport(data)

        // Fetch MTS Triage & Clinical Alerts
        const triageData = await getTriageAssessment(
          data.extracted_entities || {},
          data.extracted_entities?.symptoms || []
        )
        setTriage(triageData)

        const alertsData = await getClinicalAlerts()
        setAlerts(alertsData || [])

        setLoading(false)
        clearInterval(interval)
      } catch (err) {
        console.error(err)
        setError("Failed to load report")
        setLoading(false)
        clearInterval(interval)
      }
    }

    fetchReport()
    interval = setInterval(fetchReport, 2000)

    return () => clearInterval(interval)
  }, [reportId])

  const handleViewPdf = async () => {
    try {
      const { default: api } = await import('../services/api.js');
      const response = await api.get(`/reports/${report.id}/view`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      window.open(url, '_blank');
    } catch(err) {
      console.error(err);
      alert('Failed to load PDF');
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="animate-spin text-rose-500" size={32} />
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-red-500 gap-2">
        <AlertCircle size={24} /> {error || "Report not found"}
      </div>
    )
  }

  const entities = report.extracted_entities || {}
  const medicines = entities.medicines || []
  const labs = entities.lab_parameters || []
  const isPrescription = report.document_type === 'handwritten_prescription' || report.document_type === 'prescription' || entities.is_handwritten_prescription

  return (
    <div className="mx-auto max-w-[1600px] px-6 sm:px-8 lg:px-12 py-12 space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-widest text-rose-600">
            <Translate>Report insights</Translate>
          </p>
          <h1 className="mt-2 font-display text-3xl text-ink capitalize">
            <Translate>{report.document_type.replace('_', ' ')}</Translate>
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            {(entities.patient_name || 'Patient Report')} · <Translate>Reviewed</Translate> {entities.report_date || new Date(report.upload_date).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge tone={report.status === 'completed' ? 'success' : 'neutral'}>
            <FileText size={12} className="mr-1 inline" />
            {report.status}
          </Badge>
          <button 
            onClick={handleViewPdf}
            className="text-xs font-medium bg-white border border-ink/10 px-3 py-1.5 rounded-full text-ink hover:bg-porcelain transition shadow-sm"
          >
            <Translate>View Original</Translate>
          </button>
        </div>
      </div>

      {/* Feature 5: Manchester Triage System Card */}
      {triage && <MTSTriageCard triage={triage} />}

      {/* Feature 2: Proactive Clinical Alerts */}
      {alerts && alerts.length > 0 && <ClinicalAlertsCard alerts={alerts} />}

      {/* Feature 6: Handwritten Prescription Card */}
      {isPrescription && (
        <Card className="border-purple-200 bg-purple-50/50">
          <div className="flex items-start justify-between flex-wrap gap-3 pb-3 border-b border-purple-100">
            <div className="flex items-center gap-2">
              <Pill className="text-purple-600" size={20} />
              <div>
                <h3 className="font-display font-semibold text-lg text-purple-950">
                  <Translate>Physician Prescription Extraction</Translate>
                </h3>
                <p className="text-xs text-purple-800">
                  <Translate>Decoded medications, dosage, sig directions & administration instructions.</Translate>
                </p>
              </div>
            </div>
            {entities.handwritten_confidence_score && (
              <span className="text-xs font-semibold px-2.5 py-1 bg-purple-100 text-purple-800 rounded-full border border-purple-200">
                {entities.handwritten_confidence_score}% <Translate>Confidence</Translate>
              </span>
            )}
          </div>

          <div className="mt-4 space-y-4">
            {medicines.length > 0 ? (
              medicines.map((med, idx) => (
                <div key={idx} className="bg-white p-4 rounded-xl border border-purple-100 shadow-sm space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-ink text-base"><Translate>{med.name}</Translate></span>
                    {med.dosage && (
                      <span className="text-xs font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full">
                        <Translate>{med.dosage}</Translate>
                      </span>
                    )}
                  </div>
                  {med.sig && (
                    <p className="text-xs text-ink/90 font-medium bg-porcelain p-2.5 rounded-lg border border-ink/5">
                      <strong><Translate>Sig / Directions:</Translate> </strong> <Translate>{med.sig}</Translate>
                    </p>
                  )}
                  <div className="flex items-center gap-4 text-xs text-ink-soft pt-1">
                    {med.frequency && <span><Translate>Frequency:</Translate> <Translate>{med.frequency}</Translate></span>}
                    {med.duration && <span><Translate>Duration:</Translate> <Translate>{med.duration}</Translate></span>}
                    {med.refills && <span><Translate>Refills:</Translate> {med.refills}</span>}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-purple-900/80 bg-white/60 p-4 rounded-xl border border-purple-100"><Translate>No individual medications identified in this document.</Translate></p>
            )}
          </div>
        </Card>
      )}

      {/* Summary */}
      {(entities.diagnosis?.length > 0 || entities.symptoms?.length > 0) && (
        <Card className="border-rose-200 bg-rose-50/60">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 text-rose-600" size={20} />
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-rose-900"><Translate>Clinical Summary</Translate></p>
                {entities.summary_confidence_score !== undefined && entities.summary_confidence_score !== null && (
                  <span className="text-xs font-medium text-rose-600 bg-rose-100 px-2 py-0.5 rounded-full">
                    {entities.summary_confidence_score}% <Translate>confidence</Translate>
                  </span>
                )}
              </div>
              {entities.diagnosis?.length > 0 && (
                <p className="mt-2 text-sm leading-relaxed text-rose-900/90 font-medium">
                  <Translate>Diagnosis:</Translate> {entities.diagnosis.join(', ')}
                </p>
              )}
              {entities.symptoms?.length > 0 && (
                <p className="mt-1 text-sm leading-relaxed text-rose-900/90">
                  <Translate>Symptoms:</Translate> {entities.symptoms.join(', ')}
                </p>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Complex Terminologies Explained */}
      {entities.complex_terminologies?.length > 0 && (
        <Card className="border-blue-200 bg-blue-50/60">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 text-blue-600" size={20} />
            <div>
              <p className="text-sm font-medium text-blue-900"><Translate>Terminologies Explained</Translate></p>
              <div className="mt-3 space-y-3">
                {entities.complex_terminologies.map((item, idx) => (
                  <div key={idx} className="bg-white/60 p-3 rounded-lg border border-blue-100">
                    <div className="flex justify-between items-start">
                      <p className="font-semibold text-blue-900 text-sm">{item.term}</p>
                      {item.confidence_score !== undefined && item.confidence_score !== null && (
                        <span className="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full">
                          {item.confidence_score}% <Translate>confidence</Translate>
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-blue-800/80 mt-1">{item.explanation}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Demographics & Recommendations */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <p className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
            <Ruler size={14} /> <Translate>Patient Demographics</Translate>
          </p>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between border-b border-ink/5 pb-2">
              <dt className="text-ink-soft"><Translate>Name</Translate></dt>
              <dd className="font-medium text-ink"><Translate>{entities.patient_name || 'Not specified in report'}</Translate></dd>
            </div>
            <div className="flex justify-between border-b border-ink/5 pb-2">
              <dt className="text-ink-soft"><Translate>Age</Translate></dt>
              <dd className="font-medium text-ink"><Translate>{entities.patient_age ? `${entities.patient_age} yrs` : 'Not specified'}</Translate></dd>
            </div>
            <div className="flex justify-between border-b border-ink/5 pb-2">
              <dt className="text-ink-soft"><Translate>Gender</Translate></dt>
              <dd className="font-medium text-ink capitalize"><Translate>{entities.patient_gender || 'Not specified'}</Translate></dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-soft"><Translate>Hospital / Doctor</Translate></dt>
              <dd className="font-medium text-ink"><Translate>{entities.hospital || entities.doctor_name || 'Not specified'}</Translate></dd>
            </div>
          </dl>
        </Card>

        {entities.doctor_recommendations?.length > 0 && (
          <Card>
            <p className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
              <ListTree size={14} /> <Translate>Recommendations</Translate>
            </p>
            <ul className="list-disc pl-5 space-y-2 text-sm text-ink/80">
              {entities.doctor_recommendations.map((rec, i) => (
                <li key={i}><Translate>{rec}</Translate></li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {/* Lab parameters */}
      {labs.length > 0 && (
        <Card>
          <p className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-ink-soft">
            <ListTree size={14} /> <Translate>Lab Parameters</Translate>
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            {labs.map((lab, i) => (
              <div key={i} className={`p-4 rounded-xl border ${lab.is_abnormal ? 'border-rose-200 bg-rose-50/30' : 'border-ink/5 bg-porcelain/30'}`}>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-medium text-ink text-sm"><Translate>{lab.name}</Translate></span>
                  <div className="flex gap-1.5 items-center">
                    {lab.confidence_score !== undefined && lab.confidence_score !== null && (
                      <span className="text-[10px] font-medium text-ink-soft bg-ink/5 px-2 py-0.5 rounded-full">
                        {lab.confidence_score}%
                      </span>
                    )}
                    {lab.is_abnormal && <span className="text-xs font-bold text-rose-600 bg-rose-100 px-2 py-0.5 rounded-full"><Translate>Abnormal</Translate></span>}
                  </div>
                </div>
                <div className="text-xl font-display text-ink mt-2">
                  {lab.value} <span className="text-sm text-ink-soft ml-1">{lab.units}</span>
                </div>
                {lab.reference_range && (
                  <div className="text-xs text-ink-soft mt-1"><Translate>Ref:</Translate> {lab.reference_range}</div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

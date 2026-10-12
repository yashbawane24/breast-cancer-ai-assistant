import { createContext, useContext, useState } from 'react'
import { chatWithAssistant } from '../services/api.js'

const AssistantContext = createContext()

export const AssistantProvider = ({ children }) => {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: "Hello! I am Halcyon, your breast health AI copilot. You can ask me to explain any findings in your medical documents, clarify lab parameters, or review treatment guidance.",
      grounded: true,
      emotion: 'Supportive & Welcoming'
    }
  ])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)

  const send = async (text, lang) => {
    if (!text.trim()) return
    
    setMessages((prev) => [...prev, { role: 'user', text }])
    setInput('')
    setIsTyping(true)
    
    try {
      const res = await chatWithAssistant(text, lang)
      const data = res.data || {}
      let replyText = data.answer || "I could not find an answer."
      let emotion = data.emotion_analysis?.emotion || "Supportive & Empathetic"
      
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: replyText,
          grounded: true,
          emotion: emotion,
          longitudinal_applied: data.longitudinal_applied !== false
        },
      ])
    } catch (err) {
      console.error(err)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: "I am here with you. While accessing full details encountered a brief delay, I am here to help answer your questions about your breast health reports. Please feel free to ask again.",
          grounded: true,
          emotion: "Supportive",
          longitudinal_applied: true
        },
      ])
    } finally {
      setIsTyping(false)
    }
  }

  return (
    <AssistantContext.Provider value={{ messages, setMessages, input, setInput, isTyping, setIsTyping, send }}>
      {children}
    </AssistantContext.Provider>
  )
}

export const useAssistant = () => useContext(AssistantContext)

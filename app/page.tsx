'use client';

import { useState, useEffect } from 'react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Send, X, Bot, User, FileText, ExternalLink, Eye } from 'lucide-react';
import html2canvas from 'html2canvas';

interface DocumentPreview {
  url: string;
  page: number;
  title: string;
  previewUrl?: string;
  largePreviewUrl?: string;
  isLoading?: boolean;
  error?: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  documents?: DocumentPreview[];
}

interface ChatResponse {
  text: string;
  images: string[];
  experts: string[];
  documents: {
    title: string;
    url: string;
    page: number;
  }[];
}

const API_URL = 'http://localhost:8000';

const configurePdfjs = async () => {
  if (typeof window !== 'undefined') {
    const pdfjs = await import('pdfjs-dist');
    pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;
    return pdfjs;
  }
  return null;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [previews, setPreviews] = useState<Map<string, string>>(new Map());
  const [largePreviews, setLargePreviews] = useState<Map<string, string>>(new Map());
  const [loadingPreviews, setLoadingPreviews] = useState<Set<string>>(new Set());
  const [previewErrors, setPreviewErrors] = useState<Map<string, string>>(new Map());
  const [selectedPreview, setSelectedPreview] = useState<DocumentPreview | null>(null);

  const generatePreview = async (doc: DocumentPreview) => {
    const pdfjs = await configurePdfjs();
    if (!pdfjs) return;
    
    const previewKey = `${doc.url}_${doc.page}`;
    
    // Use functional updates to get latest state
    setLoadingPreviews(prev => {
      if (prev.has(previewKey) || previews.get(previewKey)) return prev;
      const next = new Set(prev);
      next.add(previewKey);
      return next;
    });
  
    try {
      const pdf = await pdfjs.getDocument({
        url: doc.url,
        disableAutoFetch: true,
        disableStream: true,
      }).promise;
  
      const page = await pdf.getPage(doc.page);
      
      // Small preview
      const smallViewport = page.getViewport({ scale: 0.5 });
      const smallCanvas = document.createElement('canvas');
      smallCanvas.width = smallViewport.width;
      smallCanvas.height = smallViewport.height;
      
      const smallContext = smallCanvas.getContext('2d');
      if (!smallContext) throw new Error('Failed to get small canvas context');
      
      await page.render({
        canvasContext: smallContext,
        viewport: smallViewport
      }).promise;
  
      // Large preview
      const largeViewport = page.getViewport({ scale: 1.5 });
      const largeCanvas = document.createElement('canvas');
      largeCanvas.width = largeViewport.width;
      largeCanvas.height = largeViewport.height;
  
      const largeContext = largeCanvas.getContext('2d');
      if (!largeContext) throw new Error('Failed to get large canvas context');
  
      await page.render({
        canvasContext: largeContext,
        viewport: largeViewport
      }).promise;
  
      setPreviews(prev => new Map(prev.set(previewKey, smallCanvas.toDataURL())));
      setLargePreviews(prev => new Map(prev.set(previewKey, largeCanvas.toDataURL())));
    } catch (error) {
      setPreviewErrors(prev => new Map(prev.set(previewKey, error instanceof Error ? error.message : 'Unknown error')));
    } finally {
      setLoadingPreviews(prev => {
        const next = new Set(prev);
        next.delete(previewKey);
        return next;
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const requestBody = { message: input };
      console.log('Requête envoyée:', requestBody);
      
      const response = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(requestBody),
      });

      console.log('Status de la réponse:', response.status);
      const responseText = await response.text();
      console.log('Réponse brute:', responseText);

      if (!response.ok) {
        throw new Error(`Erreur serveur: ${response.status} - ${responseText}`);
      }

      let rawData;
      try {
        rawData = JSON.parse(responseText);
      } catch (parseError) {
        console.error('Erreur de parsing JSON:', parseError);
        throw new Error(`Impossible de parser la réponse: ${responseText}`);
      }

      console.log('Données brutes reçues:', rawData);
      
      if (!rawData.response) {
        throw new Error('La réponse ne contient pas le champ "response" attendu');
      }

      let data: ChatResponse;
      try {
        data = JSON.parse(rawData.response);
      } catch (parseError) {
        console.error('Erreur de parsing de rawData.response:', parseError);
        throw new Error('Format de réponse invalide');
      }

      console.log('Données parsées:', data);
      console.log('Documents reçus:', data.documents);
      
      if (!data.text || !Array.isArray(data.documents)) {
        throw new Error('Format de réponse invalide: champs manquants ou invalides');
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: data.text,
        documents: data.documents.map(doc => {
          const cleanUrl = doc.url.split('#')[0].split('?')[0];
          return {
            ...doc,
            url: cleanUrl,
            previewUrl: previews.get(`${cleanUrl}_${doc.page}`)
          };
        }),
      };
      console.log('Message assistant créé:', assistantMessage);
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Erreur détaillée:', error);
      let errorMessage = "Désolé, une erreur est survenue lors de la communication avec le serveur.";
      
      if (error instanceof Error) {
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
          errorMessage = "Impossible de se connecter au serveur. Veuillez vérifier votre connexion et les paramètres CORS.";
        } else if (error.message.includes('Erreur serveur')) {
          errorMessage = `Le serveur a rencontré une erreur. ${error.message}`;
        } else if (error.message.includes('parsing')) {
          errorMessage = "Le serveur a renvoyé une réponse invalide. L'équipe technique a été notifiée.";
        }
        console.error('Message d\'erreur complet:', error.message);
      }

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: errorMessage,
      }]);
    } finally {
      setIsLoading(false);
      setInput('');
    }
  };

  const handleDocumentClick = (doc: DocumentPreview) => {
    const url = doc.url.includes('?') ? doc.url.split('?')[0] : doc.url;
    window.open(`${url}#page=${doc.page}`, '_blank', 'noopener,noreferrer');
  };

  const handlePreviewClick = (doc: DocumentPreview) => {
    const cleanUrl = doc.url.split('#')[0].split('?')[0];
    const previewKey = `${cleanUrl}_${doc.page}`;
    const largePreviewUrl = largePreviews.get(previewKey);
    
    if (largePreviewUrl) {
      setSelectedPreview({
        ...doc,
        url: cleanUrl,
        largePreviewUrl
      });
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    
    messages.forEach(message => {
      message.documents?.forEach(doc => {
        generatePreview(doc);
      });
    });
  
    return () => controller.abort();
  }, [messages]);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        {/* Logo */}
        <div className="absolute top-6 left-6 z-10">
          <h1 className="text-4xl font-bold tracking-tight text-black" style={{ fontFamily: "'Courier New', Courier, monospace" }}>
            Ctrl+F
          </h1>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto relative">
          {messages.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center space-y-4 p-4">
                <Bot className="w-12 h-12 mx-auto text-gray-400" />
                <h2 className="text-2xl font-bold text-gray-700">How can I assist you today?</h2>
                <p className="text-gray-500 max-w-md mx-auto">
                  As your consulting assistant, I'm here to analyze documents and provide answers to your questions.
                </p>
              </div>
            </div>
          ) : (
            <div className="min-h-full w-full max-w-3xl mx-auto py-8 px-4">
              {messages.map((message, index) => (
                <div key={index} className="mb-8 last:mb-4">
                  <div className="flex items-start gap-4 group">
                    <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                      message.role === 'assistant' ? 'bg-blue-500' : 'bg-gray-500'
                    }`}>
                      {message.role === 'assistant' ? (
                        <Bot className="w-5 h-5 text-white" />
                      ) : (
                        <User className="w-5 h-5 text-white" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="prose prose-sm max-w-none">
                        <p className="text-gray-800 whitespace-pre-wrap">{message.content}</p>
                      </div>
                      {message.documents && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {message.documents.map((doc, idx) => {
                            const previewKey = `${doc.url}_${doc.page}`;
                            const previewUrl = previews.get(previewKey);
                            const isLoading = loadingPreviews.has(previewKey);
                            const error = previewErrors.get(previewKey);
                            
                            if (error) {
                              return (
                                <button
                                  key={idx}
                                  onClick={() => handleDocumentClick(doc)}
                                  className="group relative inline-flex flex-col items-center gap-2 p-2 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
                                >
                                  <div className="w-32 h-24 flex items-center justify-center bg-red-100 rounded">
                                    <FileText className="w-8 h-8 text-red-500" />
                                  </div>
                                  <span className="text-xs text-red-600 text-center max-w-[128px]">
                                    Open the PDF
                                  </span>
                                </button>
                              );
                            }
                            
                            if (isLoading) {
                              return (
                                <div
                                  key={idx}
                                  className="w-32 h-32 flex flex-col items-center justify-center bg-blue-50 rounded-lg p-2"
                                >
                                  <div className="w-24 h-24 flex items-center justify-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent"></div>
                                  </div>
                                  <span className="text-xs text-blue-600 text-center mt-2">
                                    Chargement...
                                  </span>
                                </div>
                              );
                            }

                            if (!previewUrl) return null;

                            return (
                              <div
                                key={idx}
                                className="group relative inline-flex flex-col items-center gap-2 p-2 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                              >
                                <div className="w-32 h-24 relative overflow-hidden rounded border border-blue-200">
                                  <img 
                                    src={previewUrl} 
                                    alt={`Prévisualisation de ${doc.title}`}
                                    className="w-full h-full object-contain"
                                  />
                                  <div className="absolute inset-0 flex gap-2 items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/20">
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handlePreviewClick(doc);
                                      }}
                                      className="p-1.5 bg-white rounded-full hover:bg-gray-100"
                                    >
                                      <Eye className="w-4 h-4 text-gray-700" />
                                    </button>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleDocumentClick(doc);
                                      }}
                                      className="p-1.5 bg-white rounded-full hover:bg-gray-100"
                                    >
                                      <ExternalLink className="w-4 h-4 text-gray-700" />
                                    </button>
                                  </div>
                                </div>
                                <span className="text-xs text-blue-600 text-center max-w-[128px] truncate">
                                  {doc.title} - Page {doc.page}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex items-start gap-4 mb-8">
                  <div className="shrink-0 w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                  <div className="flex items-center gap-1 px-3 py-2 bg-gray-100 rounded-lg">
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t bg-white p-4 md:p-6">
          <div className="max-w-3xl mx-auto">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Message Ctrl+F"
                className="flex-1"
                disabled={isLoading}
              />
              <Button 
                type="submit" 
                variant="default"
                size="default"
                disabled={!input.trim()}
                className="shrink-0 bg-blue-500 hover:bg-blue-600"
              >
                {isLoading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </form>
            <p className="text-xs text-gray-500 mt-2 text-center">
              Empowering your consulting missions with cutting-edge AI intelligence.
            </p>
          </div>
        </div>
      </div>

      {selectedPreview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="font-semibold text-lg">
                {selectedPreview.title} - Page {selectedPreview.page}
              </h3>
              <button
                onClick={() => setSelectedPreview(null)}
                className="p-1 hover:bg-gray-100 rounded-full"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <img
                src={selectedPreview.largePreviewUrl}
                alt={`Grande prévisualisation de ${selectedPreview.title}`}
                className="max-w-full h-auto mx-auto"
              />
            </div>
            <div className="p-4 border-t flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setSelectedPreview(null)}
              >
                Fermer
              </Button>
              <Button
                onClick={() => handleDocumentClick(selectedPreview)}
                className="bg-blue-500 hover:bg-blue-600 text-white"
              >
                Ouvrir le PDF
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react'
import { uploadPlan } from '../services/api'

function UploadPlan({ onUploadSuccess }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      if (selectedFile.name.endsWith('.xlsx') || selectedFile.name.endsWith('.xls') || selectedFile.name.endsWith('.csv')) {
        setFile(selectedFile)
        setMessage({ type: '', text: '' })
      } else {
        setMessage({ type: 'error', text: 'El archivo debe ser Excel (.xlsx, .xls) o CSV (.csv)' })
        setFile(null)
      }
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setMessage({ type: 'error', text: 'Selecciona un archivo primero' })
      return
    }

    try {
      setUploading(true)
      setMessage({ type: '', text: '' })
      
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/d1353b8d-83b3-4a07-af72-66d85f06aec4',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'UploadPlan.jsx:handleUpload','message':'Inicio upload','data':{filename:file.name,size:file.size},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H4'})}).catch(()=>{});
      // #endregion
      
      const result = await uploadPlan(file)
      
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/d1353b8d-83b3-4a07-af72-66d85f06aec4',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'UploadPlan.jsx:handleUpload','message':'Respuesta recibida','data':{result:result},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H4'})}).catch(()=>{});
      // #endregion
      
      const rowsLoaded = result.rows_loaded || result.rows_valid + result.rows_out_of_universe
      setMessage({
        type: 'success',
        text: `Plan cargado exitosamente: ${rowsLoaded} filas cargadas, ${result.rows_valid} válidas, ${result.rows_out_of_universe} fuera de universo, ${result.missing_combos_count} combos faltantes`
      })
      
      setFile(null)
      document.getElementById('file-input').value = ''
      
      if (onUploadSuccess) {
        onUploadSuccess()
      }
    } catch (error) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/d1353b8d-83b3-4a07-af72-66d85f06aec4',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'UploadPlan.jsx:handleUpload','message':'Error capturado','data':{error:error.message,response:error.response?.data},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H4'})}).catch(()=>{});
      // #endregion
      
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Error al subir el archivo'
      })
    } finally {
      setUploading(false)
      
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/d1353b8d-83b3-4a07-af72-66d85f06aec4',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'UploadPlan.jsx:handleUpload','message':'Fin finally','data':{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H4'})}).catch(()=>{});
      // #endregion
    }
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md mb-6">
      <h3 className="text-lg font-semibold mb-4">Subir Plan (Plantilla Simple)</h3>
      
      <div className="flex items-center space-x-4">
        <div className="flex-1">
          <input
            id="file-input"
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={handleFileChange}
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-full file:border-0
              file:text-sm file:font-semibold
              file:bg-blue-50 file:text-blue-700
              hover:file:bg-blue-100"
            disabled={uploading}
          />
        </div>
        
        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          {uploading ? 'Subiendo...' : 'Subir Plan (Plantilla Simple)'}
        </button>
      </div>
      
      {message.text && (
        <div className={`mt-4 p-3 rounded-md ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-800 border border-green-200' 
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}
    </div>
  )
}

export default UploadPlan

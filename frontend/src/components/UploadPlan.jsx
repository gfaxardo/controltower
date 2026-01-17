import { useState } from 'react'
import { uploadPlan, uploadPlanRuta27 } from '../services/api'

function UploadPlan({ onUploadSuccess }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })
  const [replaceAll, setReplaceAll] = useState(false)

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

  const detectFormat = async (file) => {
    // Leer primera línea del CSV para detectar formato
    if (file.name.endsWith('.csv')) {
      return new Promise((resolve) => {
        const reader = new FileReader()
        reader.onload = (e) => {
          const firstLine = e.target.result.split('\n')[0].toLowerCase()
          // Formato Ruta 27: tiene year, month, trips_plan, active_drivers_plan
          if (firstLine.includes('year') && firstLine.includes('month') && 
              (firstLine.includes('trips_plan') || firstLine.includes('active_drivers_plan'))) {
            resolve('ruta27')
          } else {
            resolve('simple')
          }
        }
        reader.readAsText(file.slice(0, 1024)) // Solo leer primeros 1KB
      })
    }
    return 'simple' // Excel siempre usa formato simple
  }

  const handleUpload = async () => {
    if (!file) {
      setMessage({ type: 'error', text: 'Selecciona un archivo primero' })
      return
    }

    try {
      setUploading(true)
      setMessage({ type: '', text: '' })
      
      // Detectar formato del archivo
      const format = await detectFormat(file)
      
      let result
      if (format === 'ruta27') {
        // Usar endpoint Ruta 27
        result = await uploadPlanRuta27(file, null, replaceAll)
        setMessage({
          type: 'success',
          text: result.message || `Plan cargado exitosamente: ${result.rows_inserted} registros con versión ${result.plan_version}`
        })
      } else {
        // Usar endpoint simple (formato long)
        result = await uploadPlan(file)
        const rowsLoaded = result.rows_loaded || result.rows_valid + result.rows_out_of_universe
        setMessage({
          type: 'success',
          text: `Plan cargado exitosamente: ${rowsLoaded} filas cargadas, ${result.rows_valid} válidas, ${result.rows_out_of_universe} fuera de universo, ${result.missing_combos_count} combos faltantes`
        })
      }
      
      setFile(null)
      document.getElementById('file-input').value = ''
      
      if (onUploadSuccess) {
        onUploadSuccess()
      }
    } catch (error) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Error al subir el archivo'
      })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md mb-6">
      <h3 className="text-lg font-semibold mb-4">Subir Plan (Plantilla Simple)</h3>
      
      <div className="flex items-center space-x-4 mb-4">
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
      
      {file && file.name.endsWith('.csv') && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
          <label className="flex items-center space-x-2 cursor-pointer">
            <input
              type="checkbox"
              checked={replaceAll}
              onChange={(e) => setReplaceAll(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-yellow-800">
              <strong>Reemplazar todos los planes anteriores</strong> (borra todo el historial antes de subir este plan)
            </span>
          </label>
          <p className="text-xs text-yellow-700 mt-1 ml-6">
            Por defecto, los planes se acumulan por versión. Marca esta opción solo si quieres empezar desde cero.
          </p>
        </div>
      )}
      
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

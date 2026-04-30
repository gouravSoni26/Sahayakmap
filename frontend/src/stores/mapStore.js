import { create } from 'zustand'
import { MAP_CENTER, MAP_DEFAULT_ZOOM } from '../utils/constants'

/**
 * Zustand store for shared map UI state.
 * Keeps map view, active layers, selected entities, and demo mode in sync
 * between the FloodMap and the SidePanel without prop drilling.
 */
const useMapStore = create((set) => ({
  // Map view
  center: MAP_CENTER,
  zoom: MAP_DEFAULT_ZOOM,
  setView: (center, zoom) => set({ center, zoom }),

  // Layer visibility toggles
  layers: {
    gauges: true,
    floodOverlay: true,
    assets: true,
    routes: true,
    camps: true,
    alerts: true,
    satelliteOverlay: false,
  },
  toggleLayer: (layer) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: !state.layers[layer] },
    })),

  // Selected entity (shows popup / highlights in panel)
  selectedAlert: null,
  selectedAsset: null,
  selectedGauge: null,
  setSelectedAlert: (alert) => set({ selectedAlert: alert, selectedAsset: null, selectedGauge: null }),
  setSelectedAsset: (asset) => set({ selectedAsset: asset, selectedAlert: null, selectedGauge: null }),
  setSelectedGauge: (gauge) => set({ selectedGauge: gauge, selectedAlert: null, selectedAsset: null }),
  clearSelection: () => set({ selectedAlert: null, selectedAsset: null, selectedGauge: null }),

  // Time filter for reports (hours)
  hoursFilter: 6,
  setHoursFilter: (hours) => set({ hoursFilter: hours }),

  // Severity filter
  minSeverity: 1,
  setMinSeverity: (s) => set({ minSeverity: s }),

  // Recommended action highlights (triggered from situation panel)
  highlightedAssetIds: [],
  highlightedDistrict: null,
  setHighlightedAssets: (ids) => set({ highlightedAssetIds: ids }),
  setHighlightedDistrict: (district) => set({ highlightedDistrict: district }),
  clearHighlights: () => set({ highlightedAssetIds: [], highlightedDistrict: null }),

  // Demo / simulation mode
  simulationMode: false,
  currentScenarioStep: 0,
  setSimulationMode: (enabled) => set({ simulationMode: enabled }),
  setScenarioStep: (step) => set({ currentScenarioStep: step }),
}))

export default useMapStore

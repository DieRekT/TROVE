import { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './TidesMap.css';

// Fix for default marker icons in React-Leaflet
const iconPrototype = L.Icon.Default.prototype as unknown as Record<string, unknown>;
delete iconPrototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

interface TidePoint {
  time: string;
  height: number;
  type: string;
}

interface TidesData {
  location: {
    lat: number;
    lon: number;
  };
  tides: TidePoint[];
  station_name?: string;
}

interface LocationMarkerProps {
  position: [number, number];
  onPositionChange: (lat: number, lng: number) => void;
}

function LocationMarker({ position, onPositionChange }: LocationMarkerProps) {
  const map = useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      onPositionChange(lat, lng);
      map.setView([lat, lng], map.getZoom());
    },
  });

  return position ? (
    <Marker position={position}>
      <Popup>
        <div>
          <strong>Selected Location</strong>
          <br />
          Lat: {position[0].toFixed(4)}, Lng: {position[1].toFixed(4)}
        </div>
      </Popup>
    </Marker>
  ) : null;
}

export default function TidesMap() {
  const [position, setPosition] = useState<[number, number] | null>(null);
  const [tidesData, setTidesData] = useState<TidesData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(2);

  const fetchTides = useCallback(async (lat: number, lng: number) => {
    setLoading(true);
    setError(null);
    
    try {
      // Determine API base URL
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(
        `${apiBase}/trove/tides/predictions?lat=${lat}&lon=${lng}&days=${days}`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to fetch tides: ${response.statusText}`);
      }
      
      const data: TidesData = await response.json();
      setTidesData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch tides data');
      console.error('Error fetching tides:', err);
    } finally {
      setLoading(false);
    }
  }, [days]);

  // Get user's current location on mount
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const { latitude, longitude } = pos.coords;
          setPosition([latitude, longitude]);
          fetchTides(latitude, longitude);
        },
        () => {
          // Default to a coastal location if geolocation fails
          const defaultLat = 40.7128; // New York
          const defaultLng = -74.0060;
          setPosition([defaultLat, defaultLng]);
          fetchTides(defaultLat, defaultLng);
        }
      );
    } else {
      // Default location
      const defaultLat = 40.7128;
      const defaultLng = -74.0060;
      setPosition([defaultLat, defaultLng]);
      fetchTides(defaultLat, defaultLng);
    }
  }, [fetchTides]);

  const handlePositionChange = (lat: number, lng: number) => {
    setPosition([lat, lng]);
    fetchTides(lat, lng);
  };

  const handleDaysChange = (newDays: number) => {
    setDays(newDays);
    if (position) {
      fetchTides(position[0], position[1]);
    }
  };

  const formatTime = (timeStr: string) => {
    try {
      const date = new Date(timeStr);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return timeStr;
    }
  };

  return (
    <div className="tides-container">
      <div className="tides-header">
        <h1>🌊 Tides Predictions</h1>
        <p>Click on the map to select a location and view tide predictions</p>
        {tidesData?.station_name && (
          <p className="station-name">Station: {tidesData.station_name}</p>
        )}
      </div>

      <div className="tides-controls">
        <label>
          Days to predict:
          <select value={days} onChange={(e) => handleDaysChange(Number(e.target.value))}>
            <option value={1}>1 day</option>
            <option value={2}>2 days</option>
            <option value={3}>3 days</option>
            <option value={7}>7 days</option>
          </select>
        </label>
      </div>

      <div className="tides-layout">
        <div className="map-container">
          {position && (
            <MapContainer
              center={position}
              zoom={10}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <LocationMarker position={position} onPositionChange={handlePositionChange} />
            </MapContainer>
          )}
        </div>

        <div className="tides-data">
          {loading && <div className="loading">Loading tides data...</div>}
          {error && <div className="error">Error: {error}</div>}
          
          {tidesData && !loading && !error && (
            <>
              <div className="tides-summary">
                <h2>Tide Predictions</h2>
                <p className="location-info">
                  Location: {tidesData.location.lat.toFixed(4)}, {tidesData.location.lon.toFixed(4)}
                </p>
              </div>
              
              <div className="tides-list">
                {tidesData.tides.map((tide, index) => (
                  <div
                    key={index}
                    className={`tide-item ${tide.type === 'high' ? 'high-tide' : 'low-tide'}`}
                  >
                    <div className="tide-type">
                      {tide.type === 'high' ? '⬆️ High' : '⬇️ Low'} Tide
                    </div>
                    <div className="tide-time">{formatTime(tide.time)}</div>
                    <div className="tide-height">
                      {tide.height > 0 ? '+' : ''}
                      {tide.height.toFixed(2)} m
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}



"use client";

import { useState, useEffect } from "react";
import { Activity, Cpu, Thermometer, Gauge, AlertTriangle } from "lucide-react";

interface SensorData {
  timestamp: string;
  temperature: number;
  pressure: number;
  motor_rpm: number;
  conveyor_speed: number;
  batch_count: number;
  status: string;
}

export default function Dashboard() {
  const [sensorData, setSensorData] = useState<SensorData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/sensors");
        const data = await res.json();
        setSensorData(data);
        setLoading(false);
      } catch (error) {
        console.error("Failed to fetch sensor data:", error);
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white text-xl">Loading automation dashboard...</div>
      </div>
    );
  }

  const isWarning = sensorData?.status === "warning";

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Automation Dashboard</h1>
          <p className="text-gray-400">
            Real-time PLC monitoring • Last updated: {sensorData?.timestamp}
          </p>
        </div>

        {/* Status Banner */}
        {isWarning && (
          <div className="mb-6 bg-yellow-900/50 border border-yellow-500 rounded-lg p-4 flex items-center gap-3">
            <AlertTriangle className="text-yellow-500" size={24} />
            <span className="text-yellow-200">System warning detected</span>
          </div>
        )}

        {/* Sensor Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <MetricCard
            title="Temperature"
            value={sensorData?.temperature}
            unit="°C"
            icon={<Thermometer size={24} />}
            color="text-red-400"
          />
          <MetricCard
            title="Pressure"
            value={sensorData?.pressure}
            unit="kPa"
            icon={<Gauge size={24} />}
            color="text-blue-400"
          />
          <MetricCard
            title="Motor RPM"
            value={sensorData?.motor_rpm}
            unit="RPM"
            icon={<Activity size={24} />}
            color="text-green-400"
          />
          <MetricCard
            title="Conveyor Speed"
            value={sensorData?.conveyor_speed}
            unit="m/s"
            icon={<Cpu size={24} />}
            color="text-purple-400"
          />
        </div>

        {/* Batch Counter */}
        <div className="bg-gray-800 rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Production Monitor</h2>
          <div className="flex items-center gap-4">
            <div className="text-4xl font-bold text-cyan-400">
              {sensorData?.batch_count}
            </div>
            <div className="text-gray-400">/ 10 parts per batch</div>
          </div>
          <div className="mt-4 bg-gray-700 rounded-full h-3 overflow-hidden">
            <div
              className="bg-cyan-500 h-full transition-all duration-500"
              style={{ width: `${((sensorData?.batch_count || 0) / 10) * 100}%` }}
            />
          </div>
        </div>

        {/* PLC Status */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">System Status</h2>
          <div className="grid grid-cols-3 gap-4">
            <StatusItem label="PLC 1 (Motor)" status="Running" />
            <StatusItem label="PLC 2 (Conveyor)" status="Running" />
            <StatusItem label="PLC 3 (Traffic)" status="Running" />
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>Automation Dashboard • Built with Next.js + FastAPI + Supabase</p>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  unit,
  icon,
  color,
}: {
  title: string;
  value: number | undefined;
  unit: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <div className="flex items-center gap-3 mb-2">
        <div className={color}>{icon}</div>
        <h3 className="text-gray-400 text-sm">{title}</h3>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-bold">{value?.toFixed(1) || "--"}</span>
        <span className="text-gray-500">{unit}</span>
      </div>
    </div>
  );
}

function StatusItem({ label, status }: { label: string; status: string }) {
  const isRunning = status === "Running";
  return (
    <div className="bg-gray-700 rounded-lg p-4 flex items-center justify-between">
      <span className="text-gray-300">{label}</span>
      <span className={`flex items-center gap-2 ${isRunning ? "text-green-400" : "text-red-400"}`}>
        <span className={`w-2 h-2 rounded-full ${isRunning ? "bg-green-400" : "bg-red-400"}`} />
        {status}
      </span>
    </div>
  );
}

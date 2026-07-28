"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import exifr from "exifr";
import { identifyFish, createObservation, type PredictionResult, type IdentificationResponse } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";

export function FishUploader() {
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IdentificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exifCoords, setExifCoords] = useState<{ latitude: number; longitude: number } | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setPreview(URL.createObjectURL(file));
    setResult(null);
    setError(null);
    setSaved(false);
    setExifCoords(null);
    setLoading(true);

    // Extract GPS from image EXIF in parallel with the identify call
    const [data, gps] = await Promise.allSettled([
      identifyFish(file, 5),
      exifr.gps(file),
    ]);

    if (gps.status === "fulfilled" && gps.value?.latitude != null) {
      setExifCoords({ latitude: gps.value.latitude, longitude: gps.value.longitude });
    }

    if (data.status === "fulfilled") {
      setResult(data.value);
    } else {
      setError(data.reason instanceof Error ? data.reason.message : "Identification failed");
    }

    setLoading(false);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"] },
    maxSize: 20 * 1024 * 1024,
    multiple: false,
  });

  async function saveObservation() {
    if (!result) return;
    const top = result.predictions[0];
    if (!top) return;
    setSaving(true);
    try {
      let latitude = exifCoords?.latitude ?? null;
      let longitude = exifCoords?.longitude ?? null;

      if (latitude == null && navigator.geolocation) {
        try {
          const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
          );
          latitude = pos.coords.latitude;
          longitude = pos.coords.longitude;
        } catch {
          // location denied or unavailable — save without coordinates
        }
      }

      await createObservation({
        speciesName: top.speciesName,
        scientificName: top.scientificName,
        topConfidence: top.confidence,
        imageStorageKey: result.imageKey,
        latitude,
        longitude,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save observation");
    } finally {
      setSaving(false);
    }
  }

  const loggedIn = isLoggedIn();

  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto p-6">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400"}`}
      >
        <input {...getInputProps()} />
        {preview ? (
          <img src={preview} alt="Upload preview" className="max-h-64 mx-auto rounded-lg object-contain" />
        ) : (
          <p className="text-gray-500 text-lg">
            {isDragActive ? "Drop your fish photo here" : "Drag & drop a fish photo, or click to select"}
          </p>
        )}
      </div>

      {loading && (
        <div className="text-center text-blue-600 font-medium animate-pulse">Identifying species...</div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
      )}

      {result && result.isFish === false && (
        <div className="bg-orange-50 border border-orange-300 rounded-lg p-4 text-orange-800 text-center">
          🐟 That doesn&apos;t look like a fish. Try uploading a clear photo of a fish.
        </div>
      )}

      {result && result.isFish !== false && (
        <div className="flex flex-col gap-3">
          {result.uncertain && (
            <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-3 text-yellow-800 text-sm">
              Low confidence — consider using a clearer photo
            </div>
          )}
          {result.predictions.map((p) => (
            <PredictionCard key={p.rank} prediction={p} />
          ))}

          {loggedIn && !saved && (
            <div className="flex flex-col gap-1">
              {exifCoords && (
                <p className="text-xs text-gray-400 text-center">
                  GPS from photo: {exifCoords.latitude.toFixed(4)}, {exifCoords.longitude.toFixed(4)}
                </p>
              )}
              <button
                onClick={saveObservation}
                disabled={saving}
                className="mt-1 w-full bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save top result as observation"}
              </button>
            </div>
          )}
          {saved && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-green-700 text-sm text-center">
              Observation saved! View it in <a href="/observations" className="underline font-medium">My Observations</a>.
            </div>
          )}
          {!loggedIn && (
            <p className="text-center text-sm text-gray-400">
              <a href="/login" className="text-blue-500 underline">Sign in</a> to save this observation
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function formatSpeciesName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

const MEDALS = ["🥇", "🥈", "🥉"];

function conservationIcon(status: string): string {
  if (/Endangered/i.test(status)) return "🔴";
  if (/Vulnerable|Threatened/i.test(status)) return "🟡";
  return "🟢";
}

function PredictionCard({ prediction }: { prediction: PredictionResult }) {
  const pct = Math.round(prediction.confidence * 100);
  const barColor = pct >= 85 ? "bg-green-500" : pct >= 50 ? "bg-yellow-400" : "bg-red-400";
  const medal = MEDALS[prediction.rank - 1] ?? "";

  return (
    <div className="border rounded-xl p-4 flex flex-col gap-2 shadow-sm">
      <div className="flex justify-between items-start">
        <div>
          <p className="font-semibold text-gray-900">
            {medal && <span className="mr-1">{medal}</span>}
            {formatSpeciesName(prediction.speciesName)}
          </p>
          <p className="text-sm text-gray-500 italic">{prediction.scientificName}</p>
        </div>
        <span className="text-sm font-medium text-gray-700">{pct}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={`h-2 rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex flex-col gap-1 text-sm text-gray-700">
        {prediction.habitat && (
          <p><span className="font-medium">Habitat:</span> {prediction.habitat}</p>
        )}
        {prediction.diet && (
          <p><span className="font-medium">Diet:</span> {prediction.diet}</p>
        )}
        {prediction.maxSizeCm != null && (
          <p><span className="font-medium">Max size:</span> {prediction.maxSizeCm} cm</p>
        )}
        {prediction.conservationStatus && (
          <p>
            <span className="font-medium">Conservation:</span>{" "}
            {conservationIcon(prediction.conservationStatus)} {prediction.conservationStatus}
          </p>
        )}
      </div>
      {prediction.description && (
        <p className="text-sm text-gray-600">{prediction.description}</p>
      )}
      {prediction.funFact && (
        <p className="text-sm bg-blue-50 border border-blue-100 rounded-lg p-2 text-blue-800">
          💡 {prediction.funFact}
        </p>
      )}
    </div>
  );
}

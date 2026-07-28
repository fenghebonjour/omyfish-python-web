import { FishUploader } from "@/components/FishUploader";

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-3xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-center text-gray-900 mb-2">OMyFish</h1>
        <p className="text-center text-gray-500 mb-10">Upload a photo to identify your fish</p>
        <FishUploader />
      </div>
    </main>
  );
}

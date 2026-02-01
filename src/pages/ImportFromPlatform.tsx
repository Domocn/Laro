import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { 
  Upload, 
  FileJson, 
  ChefHat, 
  Loader2, 
  Check, 
  AlertCircle,
  ArrowLeft,
  FileText,
  Download
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

const platforms = [
  {
    id: 'paprika',
    name: 'Paprika',
    description: 'Import from Paprika Recipe Manager export',
    icon: '🌶️',
    format: 'JSON export from Paprika app',
    instructions: 'In Paprika: Settings > Export > Export as JSON'
  },
  {
    id: 'cookmate',
    name: 'Cookmate / Recipe Keeper',
    description: 'Import from Cookmate or Recipe Keeper',
    icon: '📚',
    format: 'JSON or backup file',
    instructions: 'Export your recipes as JSON from the app settings'
  },
  {
    id: 'json',
    name: 'Generic JSON',
    description: 'Import from any JSON format',
    icon: '📄',
    format: 'Standard recipe JSON',
    instructions: 'Use Laro format or any structured recipe JSON'
  }
];

export const ImportFromPlatform = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [selectedPlatform, setSelectedPlatform] = useState(null);
  const [jsonData, setJsonData] = useState('');
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      setJsonData(text);
      
      // Try to parse and show preview
      try {
        const parsed = JSON.parse(text);
        const count = Array.isArray(parsed) ? parsed.length : 1;
        toast.success(`Loaded file with ${count} recipe(s)`);
      } catch {
        toast.error('File does not contain valid JSON');
      }
    } catch (err) {
      toast.error('Failed to read file');
    }
  };

  const handleImport = async () => {
    if (!selectedPlatform || !jsonData.trim()) {
      toast.error('Please select a platform and provide data');
      return;
    }

    setImporting(true);
    setResult(null);

    try {
      const response = await api.post('/import/platform', {
        platform: selectedPlatform,
        data: jsonData
      });

      setResult({
        success: true,
        imported: response.data.imported,
        errors: response.data.errors || []
      });

      toast.success(`Successfully imported ${response.data.imported} recipe(s)!`);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Import failed';
      setResult({
        success: false,
        error: errorMsg
      });
      toast.error(errorMsg);
    } finally {
      setImporting(false);
    }
  };

  const sampleFormat = {
    paprika: `[
  {
    "name": "Pasta Carbonara",
    "description": "Classic Italian pasta",
    "ingredients": "400g spaghetti\\n200g guanciale\\n4 egg yolks\\n100g pecorino",
    "directions": "Cook pasta.\\nFry guanciale.\\nMix eggs with cheese.\\nCombine all.",
    "prep_time": "10 minutes",
    "cook_time": "20 minutes",
    "servings": "4",
    "categories": ["Italian", "Pasta"]
  }
]`,
    cookmate: `[
  {
    "title": "Pasta Carbonara",
    "description": "Classic Italian pasta",
    "ingredients": [
      {"name": "spaghetti", "amount": "400", "unit": "g"},
      {"name": "guanciale", "amount": "200", "unit": "g"}
    ],
    "instructions": ["Cook pasta", "Fry guanciale", "Combine"],
    "prep_time": 10,
    "cook_time": 20,
    "servings": 4,
    "category": "Italian",
    "tags": ["pasta", "quick"]
  }
]`,
    json: `[
  {
    "title": "Recipe Name",
    "description": "Description",
    "ingredients": [
      {"name": "ingredient", "amount": "1", "unit": "cup"}
    ],
    "instructions": ["Step 1", "Step 2"],
    "prep_time": 15,
    "cook_time": 30,
    "servings": 4,
    "category": "Dinner",
    "tags": ["tag1", "tag2"]
  }
]`
  };

  return (
    <div className="min-h-screen bg-cream-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <Button
            variant="ghost"
            onClick={() => navigate('/recipes')}
            className="mb-4"
            data-testid="back-to-recipes-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Recipes
          </Button>
          
          <h1 className="text-3xl font-bold text-mise-800 flex items-center gap-3">
            <Download className="w-8 h-8" />
            Import Recipes
          </h1>
          <p className="text-mise-600 mt-2">
            Import your recipes from other apps or JSON files
          </p>
        </motion.div>

        {/* Platform Selection */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8"
        >
          {platforms.map((platform) => (
            <Card
              key={platform.id}
              className={`cursor-pointer transition-all hover:shadow-md ${
                selectedPlatform === platform.id 
                  ? 'ring-2 ring-mise-500 bg-mise-50' 
                  : 'hover:bg-cream-100'
              }`}
              onClick={() => setSelectedPlatform(platform.id)}
              data-testid={`platform-${platform.id}`}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{platform.icon}</span>
                  <CardTitle className="text-lg">{platform.name}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription>{platform.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </motion.div>

        {/* Import Form */}
        {selectedPlatform && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileJson className="w-5 h-5" />
                  Import from {platforms.find(p => p.id === selectedPlatform)?.name}
                </CardTitle>
                <CardDescription>
                  {platforms.find(p => p.id === selectedPlatform)?.instructions}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* File Upload */}
                <div>
                  <Label>Upload JSON File</Label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".json"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <Button
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full mt-2 h-20 border-dashed"
                    data-testid="upload-file-btn"
                  >
                    <Upload className="w-5 h-5 mr-2" />
                    Click to upload or drag & drop
                  </Button>
                </div>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white px-2 text-muted-foreground">Or paste JSON</span>
                  </div>
                </div>

                {/* JSON Textarea */}
                <div>
                  <Label>Recipe Data (JSON)</Label>
                  <Textarea
                    value={jsonData}
                    onChange={(e) => setJsonData(e.target.value)}
                    placeholder="Paste your recipe JSON here..."
                    className="mt-2 h-48 font-mono text-sm"
                    data-testid="json-input"
                  />
                </div>

                {/* Sample Format */}
                <details className="bg-mise-50 rounded-lg p-4">
                  <summary className="cursor-pointer text-sm font-medium text-mise-700">
                    View expected format
                  </summary>
                  <pre className="mt-2 text-xs overflow-x-auto p-2 bg-white rounded border">
                    {sampleFormat[selectedPlatform]}
                  </pre>
                </details>

                {/* Import Button */}
                <Button
                  onClick={handleImport}
                  disabled={importing || !jsonData.trim()}
                  className="w-full bg-mise-600 hover:bg-mise-700"
                  data-testid="import-btn"
                >
                  {importing ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      <ChefHat className="w-4 h-4 mr-2" />
                      Import Recipes
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Result */}
            {result && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
              >
                <Card className={result.success ? 'border-green-500' : 'border-red-500'}>
                  <CardContent className="pt-6">
                    {result.success ? (
                      <div className="text-center">
                        <Check className="w-12 h-12 text-green-500 mx-auto mb-4" />
                        <h3 className="text-xl font-semibold text-green-700">
                          Import Successful!
                        </h3>
                        <p className="text-mise-600 mt-2">
                          {result.imported} recipe(s) have been added to your collection.
                        </p>
                        {result.errors?.length > 0 && (
                          <div className="mt-4 text-left bg-yellow-50 p-4 rounded-lg">
                            <p className="text-sm font-medium text-yellow-700">
                              Some items had issues:
                            </p>
                            <ul className="text-sm text-yellow-600 mt-1 list-disc list-inside">
                              {result.errors.map((err, i) => (
                                <li key={i}>{err}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        <Button
                          onClick={() => navigate('/recipes')}
                          className="mt-6 bg-mise-600 hover:bg-mise-700"
                          data-testid="view-recipes-btn"
                        >
                          View Your Recipes
                        </Button>
                      </div>
                    ) : (
                      <div className="text-center">
                        <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                        <h3 className="text-xl font-semibold text-red-700">
                          Import Failed
                        </h3>
                        <p className="text-mise-600 mt-2">{result.error}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default ImportFromPlatform;

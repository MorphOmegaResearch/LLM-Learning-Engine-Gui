#!/usr/bin/env python3
"""
Texture Collage Cutter & Profiler
A CLI tool for texture analysis and image sectioning for animation workflows
"""

import argparse
import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False
    print("Missing dependencies. Install: pip install Pillow numpy")
    sys.exit(1)

# ============================================================================
# Configuration & Storage System
# ============================================================================

class TextureStorage:
    """Manages storage of texture profiles and image collections"""
    
    def __init__(self, storage_path: str = "~/.texture_tool"):
        self.base_path = Path(storage_path).expanduser()
        self.profiles_path = self.base_path / "profiles"
        self.collections_path = self.base_path / "collections"
        self.workflows_path = self.base_path / "workflows"
        
        for path in [self.base_path, self.profiles_path, self.collections_path, self.workflows_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def list_images(self, directory: Optional[str] = None) -> List[str]:
        """List all PNG images in directory or storage"""
        if directory:
            search_dir = Path(directory)
        else:
            search_dir = self.collections_path
        
        if not search_dir.exists():
            return []
        
        png_files = list(search_dir.glob("*.png"))
        jpg_files = list(search_dir.glob("*.jpg"))
        all_files = sorted(png_files + jpg_files)
        
        return [str(f) for f in all_files]
    
    def save_profile(self, image_path: str, profile_data: Dict) -> str:
        """Save texture profile to storage"""
        image_name = Path(image_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_file = self.profiles_path / f"{image_name}_{timestamp}.json"
        
        with open(profile_file, 'w') as f:
            json.dump(profile_data, f, indent=2)
        
        return str(profile_file)
    
    def list_profiles(self) -> List[str]:
        """List all stored texture profiles"""
        profiles = sorted(self.profiles_path.glob("*.json"))
        return [str(p) for p in profiles]
    
    def save_workflow(self, name: str, workflow_data: Dict) -> str:
        """Save a workflow configuration"""
        workflow_file = self.workflows_path / f"{name}.json"
        
        with open(workflow_file, 'w') as f:
            json.dump(workflow_data, f, indent=2)
        
        return str(workflow_file)
    
    def list_workflows(self) -> List[str]:
        """List all stored workflows"""
        workflows = sorted(self.workflows_path.glob("*.json"))
        return [str(w) for w in workflows]
    
    def store_image(self, image_path: str, category: str = "uncategorized") -> str:
        """Store image in collections"""
        source_path = Path(image_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        category_path = self.collections_path / category
        category_path.mkdir(exist_ok=True)
        
        dest_path = category_path / source_path.name
        shutil.copy2(source_path, dest_path)
        
        return str(dest_path)
    
    def remove_image(self, image_path: str) -> bool:
        """Remove image from storage"""
        path = Path(image_path)
        if path.exists() and self.base_path in path.parents:
            path.unlink()
            return True
        return False

# ============================================================================
# Texture Profiler
# ============================================================================

class TextureProfiler:
    """Analyzes texture properties of images"""
    
    def __init__(self):
        self.storage = TextureStorage()
    
    def profile_image(self, image_path: str, save_profile: bool = True) -> Dict:
        """Generate comprehensive texture profile"""
        try:
            img = Image.open(image_path)
        except Exception as e:
            raise ValueError(f"Cannot open image: {e}")
        
        # Convert to numpy array for analysis
        if img.mode != 'RGB':
            img_rgb = img.convert('RGB')
        else:
            img_rgb = img
        
        img_array = np.array(img_rgb)
        
        # Basic image properties
        profile = {
            'file': image_path,
            'dimensions': img.size,
            'mode': img.mode,
            'format': img.format,
            'has_alpha': img.mode in ('RGBA', 'LA', 'PA'),
            'created': datetime.now().isoformat(),
            'analysis': {}
        }
        
        # Color analysis
        profile['analysis']['color'] = self._analyze_colors(img_array)
        
        # Edge analysis
        profile['analysis']['edges'] = self._analyze_edges(img_array)
        
        # Texture analysis
        profile['analysis']['texture'] = self._analyze_texture(img_array)
        
        # Transparency analysis
        if profile['has_alpha']:
            profile['analysis']['transparency'] = self._analyze_transparency(img)
        
        # Save profile if requested
        if save_profile:
            profile_path = self.storage.save_profile(image_path, profile)
            profile['profile_path'] = profile_path
        
        return profile
    
    def _analyze_colors(self, img_array: np.ndarray) -> Dict:
        """Analyze color distribution"""
        # Calculate mean and std for each channel
        means = img_array.mean(axis=(0, 1))
        stds = img_array.std(axis=(0, 1))
        
        # Simple dominant color detection
        reshaped = img_array.reshape(-1, 3)
        unique_colors, counts = np.unique(reshaped, axis=0, return_counts=True)
        dominant_idx = counts.argmax()
        
        return {
            'mean_rgb': means.tolist(),
            'std_rgb': stds.tolist(),
            'dominant_color': unique_colors[dominant_idx].tolist(),
            'unique_colors': len(unique_colors),
            'color_entropy': float(np.std(means))
        }
    
    def _analyze_edges(self, img_array: np.ndarray) -> Dict:
        """Analyze edge content"""
        # Convert to grayscale for edge detection
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2).astype(np.uint8)
        else:
            gray = img_array
        
        # Simple edge detection using Sobel
        from scipy import ndimage
        sobel_x = ndimage.sobel(gray, axis=0)
        sobel_y = ndimage.sobel(gray, axis=1)
        edge_magnitude = np.hypot(sobel_x, sobel_y)
        
        edge_threshold = edge_magnitude.mean() + edge_magnitude.std()
        edge_pixels = np.sum(edge_magnitude > edge_threshold)
        total_pixels = gray.size
        
        return {
            'edge_density': float(edge_pixels / total_pixels),
            'edge_variance': float(edge_magnitude.var()),
            'edge_threshold': float(edge_threshold)
        }
    
    def _analyze_texture(self, img_array: np.ndarray) -> Dict:
        """Analyze texture properties"""
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array
        
        # Calculate texture uniformity
        from scipy import ndimage
        blurred = ndimage.gaussian_filter(gray, sigma=2)
        texture_diff = np.abs(gray - blurred)
        
        return {
            'uniformity': float(texture_diff.mean()),
            'contrast': float(gray.std()),
            'brightness': float(gray.mean())
        }
    
    def _analyze_transparency(self, img: Image.Image) -> Dict:
        """Analyze alpha channel"""
        if 'A' in img.mode:
            alpha = np.array(img.getchannel('A'))
            transparent_pixels = np.sum(alpha < 255)
            total_pixels = alpha.size
            
            return {
                'transparency_ratio': float(transparent_pixels / total_pixels),
                'opaque_pixels': int(total_pixels - transparent_pixels),
                'transparent_pixels': int(transparent_pixels)
            }
        return {}

# ============================================================================
# Image Cutter
# ============================================================================

class ImageCutter:
    """Cuts images into sections using various strategies"""
    
    def __init__(self, output_dir: str = "./cuts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.storage = TextureStorage()
    
    def cut_image(self, image_path: str, strategy: str = "grid", **kwargs) -> List[str]:
        """
        Cut image using specified strategy
        
        Strategies:
        - grid: Cut into uniform grid (requires rows, cols)
        - contour: Cut around detected contours
        - color: Segment by color regions (requires threshold)
        - alpha: Cut around non-transparent areas
        - manual: Cut using specific positions (requires positions list)
        """
        strategies = {
            'grid': self._cut_grid,
            'contour': self._cut_contours,
            'color': self._cut_by_color,
            'alpha': self._cut_by_alpha,
            'manual': self._cut_manual
        }
        
        if strategy not in strategies:
            raise ValueError(f"Unknown strategy: {strategy}. Choose from: {list(strategies.keys())}")
        
        return strategies[strategy](image_path, **kwargs)
    
    def _cut_grid(self, image_path: str, rows: int = 3, cols: int = 3, 
                  margin: int = 0, overlap: int = 0) -> List[str]:
        """Cut image into uniform grid"""
        img = Image.open(image_path)
        width, height = img.size
        
        cell_w = width // cols
        cell_h = height // rows
        
        output_files = []
        
        for i in range(rows):
            for j in range(cols):
                left = j * cell_w + margin
                upper = i * cell_h + margin
                right = left + cell_w - 2*margin + overlap
                lower = upper + cell_h - 2*margin + overlap
                
                # Ensure bounds
                left = max(0, left)
                upper = max(0, upper)
                right = min(width, right)
                lower = min(height, lower)
                
                if right > left and lower > upper:
                    crop = img.crop((left, upper, right, lower))
                    output_file = self.output_dir / f"grid_{i}_{j}_{Path(image_path).stem}.png"
                    crop.save(output_file)
                    output_files.append(str(output_file))
        
        return output_files
    
    def _cut_contours(self, image_path: str, threshold: int = 128, 
                      min_size: int = 100, padding: int = 5) -> List[str]:
        """Cut around detected contours/edges"""
        import cv2
        
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        
        # Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Threshold and find contours
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        output_files = []
        
        for idx, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            
            if w >= min_size and h >= min_size:
                # Add padding
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(img.shape[1], x + w + padding)
                y2 = min(img.shape[0], y + h + padding)
                
                cropped = img[y1:y2, x1:x2]
                output_file = self.output_dir / f"contour_{idx}_{Path(image_path).stem}.png"
                cv2.imwrite(str(output_file), cropped)
                output_files.append(str(output_file))
        
        return output_files
    
    def _cut_by_color(self, image_path: str, color_tolerance: int = 30, 
                      min_area: int = 50) -> List[str]:
        """Segment image by color regions"""
        img = Image.open(image_path)
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        img_array = np.array(img)
        
        # Simple color quantization
        from sklearn.cluster import KMeans
        
        pixels = img_array.reshape(-1, 3)
        
        # Use K-means to find dominant colors
        n_colors = min(8, len(pixels) // 1000)  # Dynamic number of colors
        if n_colors < 2:
            n_colors = 2
        
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        labels = kmeans.fit_predict(pixels)
        
        output_files = []
        
        for color_idx in range(n_colors):
            mask = (labels == color_idx).reshape(img_array.shape[:2])
            
            # Find bounding box of this color region
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            
            if not np.any(rows) or not np.any(cols):
                continue
            
            y1, y2 = np.where(rows)[0][[0, -1]]
            x1, x2 = np.where(cols)[0][[0, -1]]
            
            area = (y2 - y1) * (x2 - x1)
            if area >= min_area:
                cropped = img.crop((x1, y1, x2, y2))
                output_file = self.output_dir / f"color_{color_idx}_{Path(image_path).stem}.png"
                cropped.save(output_file)
                output_files.append(str(output_file))
        
        return output_files
    
    def _cut_by_alpha(self, image_path: str, min_opacity: int = 10) -> List[str]:
        """Cut around non-transparent areas"""
        img = Image.open(image_path)
        
        if img.mode not in ('RGBA', 'LA', 'PA'):
            raise ValueError("Image must have alpha channel for alpha-based cutting")
        
        alpha = img.getchannel('A')
        alpha_array = np.array(alpha)
        
        # Find connected components of non-transparent pixels
        from scipy import ndimage
        
        mask = alpha_array > min_opacity
        labeled_array, num_features = ndimage.label(mask)
        
        output_files = []
        
        for i in range(1, num_features + 1):
            positions = np.where(labeled_array == i)
            
            if len(positions[0]) == 0:
                continue
            
            y1, y2 = positions[0].min(), positions[0].max()
            x1, x2 = positions[1].min(), positions[1].max()
            
            # Add some padding
            padding = 2
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(img.width, x2 + padding)
            y2 = min(img.height, y2 + padding)
            
            cropped = img.crop((x1, y1, x2, y2))
            output_file = self.output_dir / f"alpha_{i}_{Path(image_path).stem}.png"
            cropped.save(output_file, 'PNG')
            output_files.append(str(output_file))
        
        return output_files
    
    def _cut_manual(self, image_path: str, positions: List[Tuple], 
                    labels: Optional[List[str]] = None) -> List[str]:
        """Cut using manually specified positions"""
        img = Image.open(image_path)
        output_files = []
        
        for idx, (x1, y1, x2, y2) in enumerate(positions):
            # Validate coordinates
            x1, x2 = sorted([x1, x2])
            y1, y2 = sorted([y1, y2])
            
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img.width, x2)
            y2 = min(img.height, y2)
            
            if x2 > x1 and y2 > y1:
                cropped = img.crop((x1, y1, x2, y2))
                
                if labels and idx < len(labels):
                    label = labels[idx]
                else:
                    label = f"manual_{idx}"
                
                output_file = self.output_dir / f"{label}_{Path(image_path).stem}.png"
                cropped.save(output_file)
                output_files.append(str(output_file))
        
        return output_files

# ============================================================================
# Classification System
# ============================================================================

class TextureClassifier:
    """Classifies textures based on profiles"""
    
    def __init__(self):
        self.storage = TextureStorage()
    
    def classify_image(self, image_path: str, profile: Optional[Dict] = None) -> Dict:
        """Classify image texture type"""
        if not profile:
            profiler = TextureProfiler()
            profile = profiler.profile_image(image_path, save_profile=False)
        
        analysis = profile['analysis']
        
        # Simple classification based on texture properties
        classification = {
            'type': 'unknown',
            'confidence': 0.0,
            'characteristics': []
        }
        
        # Edge-based classification
        edge_density = analysis['edges']['edge_density']
        if edge_density > 0.3:
            classification['characteristics'].append('high_detail')
            classification['type'] = 'detailed_texture'
            classification['confidence'] = 0.8
        elif edge_density < 0.05:
            classification['characteristics'].append('flat')
            classification['type'] = 'solid_color'
            classification['confidence'] = 0.7
        
        # Color-based classification
        unique_colors = analysis['color']['unique_colors']
        if unique_colors < 10:
            classification['characteristics'].append('low_color_count')
            if classification['type'] == 'unknown':
                classification['type'] = 'simple_pattern'
                classification['confidence'] = 0.6
        
        # Transparency-based classification
        if 'transparency' in analysis:
            trans_ratio = analysis['transparency']['transparency_ratio']
            if trans_ratio > 0.5:
                classification['characteristics'].append('transparent')
                classification['type'] = 'alpha_texture'
                classification['confidence'] = 0.9
        
        # Texture uniformity
        uniformity = analysis['texture']['uniformity']
        if uniformity < 5:
            classification['characteristics'].append('uniform')
            if classification['type'] == 'unknown':
                classification['type'] = 'smooth_texture'
                classification['confidence'] = 0.7
        
        return classification

# ============================================================================
# Workflow Manager
# ============================================================================

class WorkflowManager:
    """Manages and executes texture processing workflows"""
    
    def __init__(self):
        self.storage = TextureStorage()
        self.profiler = TextureProfiler()
        self.cutter = ImageCutter()
        self.classifier = TextureClassifier()
        self.workflows = self._load_default_workflows()
    
    def _load_default_workflows(self) -> Dict:
        """Load default workflow configurations"""
        return {
            'texture_analysis': {
                'description': 'Complete texture profiling workflow',
                'steps': ['profile', 'classify', 'save'],
                'output_formats': ['json', 'txt']
            },
            'grid_cutting': {
                'description': 'Cut image into uniform grid for animation',
                'steps': ['validate', 'grid_cut', 'rename_sequential'],
                'params': {'rows': 4, 'cols': 4}
            },
            'sprite_extraction': {
                'description': 'Extract sprites using alpha channel',
                'steps': ['validate', 'alpha_cut', 'classify'],
                'params': {'min_opacity': 30}
            },
            'batch_profile': {
                'description': 'Profile multiple images in directory',
                'steps': ['list_images', 'batch_profile', 'generate_report'],
                'params': {'directory': '.'}
            }
        }
    
    def list_workflows(self, show_details: bool = False) -> List[str]:
        """List available workflows"""
        if show_details:
            result = []
            for name, config in self.workflows.items():
                result.append(f"{name}: {config['description']}")
                if 'params' in config:
                    result.append(f"  Params: {config['params']}")
            return result
        return list(self.workflows.keys())
    
    def run_workflow(self, workflow_name: str, image_path: str, **params) -> Dict:
        """Execute a workflow on an image"""
        if workflow_name not in self.workflows:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        workflow = self.workflows[workflow_name]
        results = {
            'workflow': workflow_name,
            'image': image_path,
            'timestamp': datetime.now().isoformat(),
            'steps': {}
        }
        
        # Update with provided params
        workflow_params = workflow.get('params', {}).copy()
        workflow_params.update(params)
        
        # Execute workflow steps
        for step in workflow['steps']:
            step_result = self._execute_step(step, image_path, workflow_params)
            results['steps'][step] = step_result
        
        # Save workflow result
        result_file = self.storage.save_workflow(
            f"{workflow_name}_{Path(image_path).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            results
        )
        
        results['result_file'] = result_file
        return results
    
    def _execute_step(self, step: str, image_path: str, params: Dict) -> Any:
        """Execute a single workflow step"""
        if step == 'profile':
            return self.profiler.profile_image(image_path, save_profile=True)
        
        elif step == 'classify':
            profile = self.profiler.profile_image(image_path, save_profile=False)
            return self.classifier.classify_image(image_path, profile)
        
        elif step == 'grid_cut':
            rows = params.get('rows', 3)
            cols = params.get('cols', 3)
            return self.cutter.cut_image(image_path, 'grid', rows=rows, cols=cols)
        
        elif step == 'alpha_cut':
            min_opacity = params.get('min_opacity', 10)
            return self.cutter.cut_image(image_path, 'alpha', min_opacity=min_opacity)
        
        elif step == 'contour_cut':
            threshold = params.get('threshold', 128)
            return self.cutter.cut_image(image_path, 'contour', threshold=threshold)
        
        elif step == 'validate':
            # Simple validation
            img = Image.open(image_path)
            return {
                'valid': True,
                'dimensions': img.size,
                'format': img.format,
                'mode': img.mode
            }
        
        elif step == 'save':
            return {'saved': True, 'path': image_path}
        
        elif step == 'list_images':
            directory = params.get('directory', '.')
            return self.storage.list_images(directory)
        
        else:
            return {'status': f'Unknown step: {step}'}

# ============================================================================
# Main CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Texture Collage Cutter & Profiler - CLI tool for texture analysis and image sectioning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available workflows
  %(prog)s --workflows --list
  
  # List stored images
  %(prog)s --images --list
  
  # List images in specific directory
  %(prog)s --images --list --dir ./textures
  
  # Run workflow on image
  %(prog)s --workflow sprite_extraction --image sprite_sheet.png --run
  
  # Profile an image
  %(prog)s --image texture.png --profile
  
  # Cut image with grid strategy
  %(prog)s --image collage.png --cut grid --params rows=4 cols=4
  
  # Cut with specific positions (manual)
  %(prog)s --image image.png --cut manual --positions "[(10,10,100,100),(110,10,200,100)]"
  
  # Classify texture
  %(prog)s --image material.png --classify
  
  # Store image in collection
  %(prog)s --image new_texture.png --store --category materials
  
  # Remove image from storage
  %(prog)s --remove stored_image.png
  
  # View texture profile
  %(prog)s --image textured.png --view-profile
        """
    )
    
    # Main action groups
    action_group = parser.add_argument_group('Primary Actions')
    action_group.add_argument('--workflows', '-w', action='store_true',
                            help='Workflow management operations')
    action_group.add_argument('--images', '-i', action='store_true',
                            help='Image storage operations')
    action_group.add_argument('--image', '-img', type=str,
                            help='Path to input image')
    action_group.add_argument('--profile', '-p', action='store_true',
                            help='Generate texture profile')
    action_group.add_argument('--cut', '-c', type=str,
                            choices=['grid', 'contour', 'color', 'alpha', 'manual'],
                            help='Cut image using specified strategy')
    action_group.add_argument('--classify', '-cls', action='store_true',
                            help='Classify texture type')
    action_group.add_argument('--run', '-r', action='store_true',
                            help='Run workflow')
    
    # Workflow options
    workflow_group = parser.add_argument_group('Workflow Options')
    workflow_group.add_argument('--workflow', '-wf', type=str,
                              help='Workflow name to run')
    workflow_group.add_argument('--list', '-l', action='store_true',
                              help='List items (workflows/images)')
    workflow_group.add_argument('--details', '-d', action='store_true',
                              help='Show detailed information')
    workflow_group.add_argument('--params', '-P', type=str,
                              help='Parameters for workflow/cutting (key=value,key2=value2)')
    workflow_group.add_argument('--positions', '-pos', type=str,
                              help='Manual cut positions as list of tuples [(x1,y1,x2,y2),...]')
    
    # Storage options
    storage_group = parser.add_argument_group('Storage Options')
    storage_group.add_argument('--store', '-s', action='store_true',
                             help='Store image in collection')
    storage_group.add_argument('--remove', '-rm', type=str,
                             help='Remove image from storage')
    storage_group.add_argument('--category', '-cat', type=str, default='uncategorized',
                             help='Category for storing images')
    storage_group.add_argument('--dir', '-D', type=str,
                             help='Directory for image operations')
    storage_group.add_argument('--view-profile', '-vp', action='store_true',
                             help='View saved texture profile')
    storage_group.add_argument('--output-dir', '-o', type=str, default='./output',
                             help='Output directory for cut images')
    
    # Cutting parameters
    cut_group = parser.add_argument_group('Cutting Parameters')
    cut_group.add_argument('--rows', '-R', type=int, default=3,
                         help='Rows for grid cutting')
    cut_group.add_argument('--cols', '-C', type=int, default=3,
                         help='Columns for grid cutting')
    cut_group.add_argument('--threshold', '-t', type=int, default=128,
                         help='Threshold for edge detection')
    cut_group.add_argument('--min-size', '-ms', type=int, default=100,
                         help='Minimum size for contour cutting')
    cut_group.add_argument('--color-tol', '-ct', type=int, default=30,
                         help='Color tolerance for color-based cutting')
    
    args = parser.parse_args()
    
    # Initialize managers
    storage = TextureStorage()
    workflow_mgr = WorkflowManager()
    profiler = TextureProfiler()
    cutter = ImageCutter(args.output_dir)
    classifier = TextureClassifier()
    
    # Parse parameters
    params = {}
    if args.params:
        for pair in args.params.split(','):
            if '=' in pair:
                key, value = pair.split('=', 1)
                # Try to convert to appropriate type
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                params[key] = value
    
    # Handle remove operation
    if args.remove:
        if storage.remove_image(args.remove):
            print(f"✓ Removed: {args.remove}")
        else:
            print(f"✗ Could not remove: {args.remove}")
        return
    
    # Handle list operations
    if args.list:
        if args.workflows:
            workflows = workflow_mgr.list_workflows(args.details)
            print("\nAvailable Workflows:")
            print("-" * 40)
            if args.details:
                for line in workflows:
                    print(line)
            else:
                for wf in workflows:
                    print(f"  • {wf}")
            print()
        
        elif args.images:
            images = storage.list_images(args.dir)
            print(f"\nStored Images ({'all' if not args.dir else args.dir}):")
            print("-" * 60)
            for idx, img in enumerate(images, 1):
                print(f"{idx:3d}. {img}")
            print(f"\nTotal: {len(images)} images")
        
        else:
            print("Specify --workflows or --images with --list")
        
        return
    
    # Handle workflow execution
    if args.workflow and args.run and args.image:
        print(f"Running workflow: {args.workflow} on {args.image}")
        results = workflow_mgr.run_workflow(args.workflow, args.image, **params)
        print(f"✓ Workflow completed")
        print(f"  Results saved to: {results['result_file']}")
        
        # Show summary
        if 'steps' in results:
            print("\nWorkflow Steps:")
            for step, result in results['steps'].items():
                print(f"  • {step}: {len(result) if isinstance(result, list) else 'completed'}")
        return
    
    # Handle individual operations
    if args.image:
        # Profile image
        if args.profile:
            print(f"Profiling: {args.image}")
            profile = profiler.profile_image(args.image)
            print(f"✓ Profile saved: {profile.get('profile_path', 'in memory')}")
            
            # Display summary
            print(f"\nTexture Summary:")
            print(f"  Dimensions: {profile['dimensions']}")
            print(f"  Mode: {profile['mode']}")
            print(f"  Color Analysis:")
            print(f"    • Dominant Color: {profile['analysis']['color']['dominant_color']}")
            print(f"    • Unique Colors: {profile['analysis']['color']['unique_colors']}")
        
        # Cut image
        elif args.cut:
            print(f"Cutting {args.image} using {args.cut} strategy")
            
            cut_params = {
                'rows': args.rows,
                'cols': args.cols,
                'threshold': args.threshold,
                'min_size': args.min_size,
                'color_tolerance': args.color_tol
            }
            
            # Handle manual positions
            if args.cut == 'manual' and args.positions:
                try:
                    positions = eval(args.positions)
                    if isinstance(positions, list):
                        cut_params['positions'] = positions
                except:
                    print("✗ Invalid positions format. Use [(x1,y1,x2,y2),...]")
                    return
            
            try:
                cut_files = cutter.cut_image(args.image, args.cut, **cut_params)
                print(f"✓ Created {len(cut_files)} cut images:")
                for i, f in enumerate(cut_files[:5], 1):  # Show first 5
                    print(f"  {i}. {Path(f).name}")
                if len(cut_files) > 5:
                    print(f"  ... and {len(cut_files) - 5} more")
                print(f"Output directory: {args.output_dir}")
            except Exception as e:
                print(f"✗ Cutting failed: {e}")
        
        # Classify image
        elif args.classify:
            print(f"Classifying: {args.image}")
            classification = classifier.classify_image(args.image)
            print(f"\nClassification Results:")
            print(f"  Type: {classification['type']}")
            print(f"  Confidence: {classification['confidence']:.2f}")
            if classification['characteristics']:
                print(f"  Characteristics: {', '.join(classification['characteristics'])}")
        
        # Store image
        elif args.store:
            stored_path = storage.store_image(args.image, args.category)
            print(f"✓ Stored image in category '{args.category}':")
            print(f"  {stored_path}")
        
        # View profile
        elif args.view_profile:
            profiles = storage.list_profiles()
            image_name = Path(args.image).stem
            matching = [p for p in profiles if image_name in p]
            
            if matching:
                print(f"Profiles for {args.image}:")
                for profile in matching:
                    with open(profile, 'r') as f:
                        data = json.load(f)
                    print(f"\n{Path(profile).name}:")
                    print(f"  Created: {data.get('created', 'N/A')}")
                    print(f"  Dimensions: {data.get('dimensions', 'N/A')}")
            else:
                print(f"No saved profiles found for {args.image}")
                print("Run with --profile first to create a profile")
        
        else:
            print("Specify an action: --profile, --cut, --classify, --store, or --view-profile")
    
    elif args.workflows and not args.list:
        print("Use --workflows --list to see available workflows")
        print("Use --workflow NAME --image FILE --run to execute a workflow")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    if not HAS_DEPS:
        print("Required packages not found.")
        print("Install with: pip install Pillow numpy scikit-image scikit-learn opencv-python")
        sys.exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
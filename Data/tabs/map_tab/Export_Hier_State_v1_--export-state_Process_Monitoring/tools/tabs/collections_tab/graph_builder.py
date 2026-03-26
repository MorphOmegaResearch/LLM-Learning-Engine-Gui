#!/usr/bin/env python3
"""
Knowledge Graph Builder
Builds graph structures from RAG sessions for visualization.
Part of Section 6 - Collections RAG Network Viz
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict
import math


class KnowledgeGraphBuilder:
    """
    Builds knowledge graphs from RAG session data.

    Features:
    - Node extraction from embeddings and sessions
    - Edge weight calculation based on co-occurrence
    - Topic clustering
    - Relevance scoring
    """

    def __init__(self, project_path: Path):
        """
        Initialize graph builder.

        Args:
            project_path: Path to project directory
        """
        self.project_path = project_path
        self.embeddings_path = project_path / "embeddings"
        self.knowledge_bank_path = project_path / "knowledge_bank"

        self.nodes = {}  # node_id -> node_data
        self.edges = []  # [(source_id, target_id, weight)]
        self.clusters = {}  # cluster_id -> [node_ids]

    def build_graph(self) -> Dict[str, Any]:
        """
        Build knowledge graph from project data.

        Returns:
            Dict with nodes, edges, and clusters
        """
        # Extract nodes from embeddings and knowledge bank
        self._extract_nodes()

        # Calculate edges based on co-occurrence
        self._calculate_edges()

        # Cluster by topic
        self._cluster_by_topic()

        return {
            'nodes': list(self.nodes.values()),
            'edges': self.edges,
            'clusters': self.clusters,
            'stats': {
                'total_nodes': len(self.nodes),
                'total_edges': len(self.edges),
                'total_clusters': len(self.clusters)
            }
        }

    def _extract_nodes(self):
        """Extract nodes from knowledge sources."""
        node_id = 0

        # Extract from embeddings if available
        if self.embeddings_path.exists():
            for embedding_file in self.embeddings_path.glob("*.json"):
                try:
                    with open(embedding_file, 'r') as f:
                        data = json.load(f)

                    # Create node from embedding metadata
                    node = {
                        'id': f'node_{node_id}',
                        'label': embedding_file.stem[:30],
                        'type': 'embedding',
                        'source': str(embedding_file),
                        'size': len(str(data)),  # Knowledge volume
                        'topics': self._extract_topics(data),
                        'tier': self._calculate_tier(data)
                    }

                    self.nodes[node['id']] = node
                    node_id += 1

                except Exception:
                    continue

        # Extract from knowledge bank
        if self.knowledge_bank_path.exists():
            for kb_file in self.knowledge_bank_path.glob("**/*.txt"):
                try:
                    content = kb_file.read_text()

                    node = {
                        'id': f'node_{node_id}',
                        'label': kb_file.stem[:30],
                        'type': 'knowledge',
                        'source': str(kb_file),
                        'size': len(content),
                        'topics': self._extract_topics_from_text(content),
                        'tier': 1
                    }

                    self.nodes[node['id']] = node
                    node_id += 1

                except Exception:
                    continue

        # If no nodes found, create placeholder
        if not self.nodes:
            self.nodes['node_0'] = {
                'id': 'node_0',
                'label': 'Project Root',
                'type': 'placeholder',
                'source': str(self.project_path),
                'size': 100,
                'topics': ['general'],
                'tier': 0
            }

    def _calculate_edges(self):
        """Calculate edges between nodes based on topic overlap."""
        node_list = list(self.nodes.values())

        for i, node1 in enumerate(node_list):
            for node2 in node_list[i+1:]:
                # Calculate similarity based on topic overlap
                topics1 = set(node1.get('topics', []))
                topics2 = set(node2.get('topics', []))

                if topics1 and topics2:
                    overlap = len(topics1 & topics2)
                    union = len(topics1 | topics2)

                    if overlap > 0:
                        weight = overlap / union  # Jaccard similarity
                        self.edges.append((node1['id'], node2['id'], weight))

    def _cluster_by_topic(self):
        """Cluster nodes by dominant topic."""
        topic_nodes = defaultdict(list)

        for node in self.nodes.values():
            topics = node.get('topics', ['general'])
            # Use first topic as cluster
            primary_topic = topics[0] if topics else 'general'
            topic_nodes[primary_topic].append(node['id'])

        self.clusters = dict(topic_nodes)

    def _extract_topics(self, data: Any) -> List[str]:
        """Extract topics from embedding data."""
        topics = []

        # Try to extract from metadata
        if isinstance(data, dict):
            if 'topics' in data:
                topics = data['topics']
            elif 'tags' in data:
                topics = data['tags']
            elif 'metadata' in data and isinstance(data['metadata'], dict):
                topics = data['metadata'].get('topics', [])

        # Fallback to generic
        if not topics:
            topics = ['general']

        return topics[:3]  # Max 3 topics per node

    def _extract_topics_from_text(self, text: str) -> List[str]:
        """Extract topics from text content using simple keyword matching."""
        keywords = {
            'code': ['function', 'class', 'import', 'def', 'return'],
            'data': ['dataset', 'training', 'model', 'evaluation'],
            'documentation': ['readme', 'docs', 'guide', 'tutorial'],
            'config': ['config', 'settings', 'parameters'],
            'testing': ['test', 'assert', 'verify', 'check']
        }

        text_lower = text.lower()
        found_topics = []

        for topic, terms in keywords.items():
            if any(term in text_lower for term in terms):
                found_topics.append(topic)

        return found_topics if found_topics else ['general']

    def _calculate_tier(self, data: Any) -> int:
        """Calculate knowledge tier (0-3) based on complexity."""
        # Simple heuristic based on data size and structure
        size = len(str(data))

        if size > 10000:
            return 3  # High complexity
        elif size > 5000:
            return 2  # Medium complexity
        elif size > 1000:
            return 1  # Low complexity
        else:
            return 0  # Basic

    def calculate_layout(self, nodes: List[Dict], edges: List[Tuple],
                        width: int = 800, height: int = 600) -> Dict[str, Tuple[float, float]]:
        """
        Calculate force-directed layout positions.

        Args:
            nodes: List of node dicts
            edges: List of (source, target, weight) tuples
            width: Canvas width
            height: Canvas height

        Returns:
            Dict of node_id -> (x, y) positions
        """
        # Simple force-directed layout
        positions = {}

        # Initialize random positions
        import random
        for node in nodes:
            positions[node['id']] = (
                random.randint(50, width-50),
                random.randint(50, height-50)
            )

        # Run iterations to minimize energy
        iterations = 50
        for _ in range(iterations):
            forces = defaultdict(lambda: [0.0, 0.0])

            # Repulsion between all nodes
            for i, node1 in enumerate(nodes):
                for node2 in nodes[i+1:]:
                    pos1 = positions[node1['id']]
                    pos2 = positions[node2['id']]

                    dx = pos2[0] - pos1[0]
                    dy = pos2[1] - pos1[1]
                    dist = math.sqrt(dx*dx + dy*dy) + 0.1

                    # Repulsive force
                    force = 1000 / (dist * dist)
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force

                    forces[node1['id']][0] -= fx
                    forces[node1['id']][1] -= fy
                    forces[node2['id']][0] += fx
                    forces[node2['id']][1] += fy

            # Attraction along edges
            for source_id, target_id, weight in edges:
                pos1 = positions[source_id]
                pos2 = positions[target_id]

                dx = pos2[0] - pos1[0]
                dy = pos2[1] - pos1[1]
                dist = math.sqrt(dx*dx + dy*dy) + 0.1

                # Attractive force proportional to weight
                force = dist * weight * 0.01
                fx = (dx / dist) * force
                fy = (dy / dist) * force

                forces[source_id][0] += fx
                forces[source_id][1] += fy
                forces[target_id][0] -= fx
                forces[target_id][1] -= fy

            # Update positions
            damping = 0.9
            for node in nodes:
                node_id = node['id']
                x, y = positions[node_id]
                fx, fy = forces[node_id]

                x += fx * damping
                y += fy * damping

                # Boundary check
                x = max(30, min(width-30, x))
                y = max(30, min(height-30, y))

                positions[node_id] = (x, y)

        return positions


def build_knowledge_graph(project_path: Path) -> Dict[str, Any]:
    """Build knowledge graph for project."""
    builder = KnowledgeGraphBuilder(project_path)
    return builder.build_graph()

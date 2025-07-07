import streamlit as st
from neo4j import GraphDatabase
import os
from datetime import datetime
import pickle
import networkx as nx
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
import shutil
import gc  # For garbage collection

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7690"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "12345678"
DATABASE_NAME = "expansion"

class GraphVisualizer:
    def __init__(self, uri, user, password, database):
        self.driver = None
        self.database = database
        self.snapshot_dir = os.path.join(os.path.expanduser("~"), "thesis", "graph_snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)

        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
            st.success("✅ Connected to Neo4j database successfully!")
        except Exception as e:
            st.error(f"❌ Failed to connect to Neo4j: {str(e)}")

    def close(self):
        if self.driver:
            self.driver.close()

    def save_graph_snapshot(self, snapshot_name="before_extraction"):
        """Save current graph state to file - optimized version"""
        try:
            # Get only essential data for snapshots
            nodes, relationships = self.get_graph_data_lightweight()
            snapshot_data = {
                'timestamp': datetime.now().isoformat(),
                'nodes': nodes,
                'relationships': relationships,
                'node_count': len(nodes),
                'rel_count': len(relationships)
            }

            snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_name}.pkl")
            with open(snapshot_file, 'wb') as f:
                pickle.dump(snapshot_data, f, protocol=pickle.HIGHEST_PROTOCOL)

            st.success(f"📸 Graph snapshot saved: {snapshot_name}")
            
            # Force garbage collection
            del snapshot_data
            gc.collect()
            return True
        except Exception as e:
            st.error(f"Error saving snapshot: {str(e)}")
            return False

    def load_graph_snapshot(self, snapshot_name="before_extraction"):
        """Load graph state from file"""
        try:
            snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_name}.pkl")
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'rb') as f:
                    snapshot_data = pickle.load(f)
                return snapshot_data
            else:
                st.warning(f"Snapshot file '{snapshot_name}.pkl' not found.")
                return None
        except Exception as e:
            st.error(f"Error loading snapshot: {str(e)}")
            return None

    def get_available_snapshots(self):
        """Get list of available snapshots"""
        try:
            snapshots = []
            if os.path.exists(self.snapshot_dir):
                for file in os.listdir(self.snapshot_dir):
                    if file.endswith('.pkl'):
                        snapshot_name = file.replace('.pkl', '')
                        file_path = os.path.join(self.snapshot_dir, file)
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        snapshots.append({
                            'name': snapshot_name,
                            'timestamp': file_time.strftime("%Y-%m-%d %H:%M:%S")
                        })
            return sorted(snapshots, key=lambda s: s['timestamp'], reverse=True)
        except Exception as e:
            st.error(f"Error getting snapshots: {str(e)}")
            return []

    def get_graph_data_lightweight(self, limit=1000):
        """Get essential graph data only - memory optimized"""
        if not self.driver:
            return [], []

        try:
            with self.driver.session(database=self.database) as session:
                # Get nodes with only essential fields - UPDATED to use NAME
                node_query = f"""
                MATCH (n)
                RETURN elementId(n) as node_id, 
                       labels(n) as labels,
                       coalesce(n.NAME, n.title, 'Node_' + toString(elementId(n))) as name,
                       n.source as source
                LIMIT {limit}
                """
                nodes_result = session.run(node_query)
                nodes = [record.data() for record in nodes_result]

                if not nodes:
                    return [], []

                node_ids = [node['node_id'] for node in nodes]

                # Get relationships with only essential fields
                rel_query = """
                MATCH (a)-[r]->(b)
                WHERE elementId(a) IN $node_ids AND elementId(b) IN $node_ids
                RETURN elementId(a) as source_id, elementId(b) as target_id, 
                       type(r) as rel_type,
                       r.source as rel_source
                """
                relationships_result = session.run(rel_query, node_ids=node_ids)
                relationships = [record.data() for record in relationships_result]

                return nodes, relationships

        except Exception as e:
            st.error(f"Error getting lightweight graph data: {str(e)}")
            return [], []

    def get_single_node_neighborhood(self, node_name, hops=1, max_neighbors=50):
        """Get a specific node and its immediate neighborhood from current graph"""
        if not self.driver:
            return [], []

        try:
            with self.driver.session(database=self.database) as session:
                # Find the target node first - UPDATED to use NAME
                find_node_query = """
                MATCH (target)
                WHERE (
                    any(item IN target.NAME WHERE toLower(toString(item)) = toLower($node_name))
                )
                RETURN elementId(target) as node_id, 
                       labels(target) as labels,
                       target.NAME as NAME,
                       target.source as source,
                       target.id as external_id
                LIMIT 1
                """
                
                target_result = session.run(find_node_query, node_name=node_name)
                target_record = target_result.single()
                
                if not target_record:
                    return [], []
                
                target_node_id = target_record['node_id']
                
                # Get neighborhood nodes and relationships
                neighborhood_query = f"""
                MATCH (center)-[r*1..{hops}]-(neighbor)
                WHERE elementId(center) = $target_node_id
                WITH center, neighbor, r
                LIMIT {max_neighbors}
                
                // Get all nodes in the neighborhood
                WITH collect(DISTINCT center) + collect(DISTINCT neighbor) as all_nodes
                UNWIND all_nodes as n
                WITH DISTINCT n
                
                RETURN elementId(n) as node_id,
                       labels(n) as labels,
                       n.NAME as NAME,
                       n.source as source,
                       n.id as external_id
                """
                
                nodes_result = session.run(neighborhood_query, target_node_id=target_node_id)
                nodes = [record.data() for record in nodes_result]
                
                if not nodes:
                    return [], []
                
                node_ids = [node['node_id'] for node in nodes]
                
                # Get relationships between these nodes - UPDATED to use NAME
                rel_query = """
                MATCH (a)-[r]->(b)
                WHERE elementId(a) IN $node_ids AND elementId(b) IN $node_ids
                RETURN elementId(a) as source_id, 
                       elementId(b) as target_id,
                       type(r) as rel_type,
                       r.source as rel_source,
                       coalesce(a.NAME, ['Unknown']) as source_name,
                       coalesce(b.NAME, ['Unknown']) as target_name
                """
                
                relationships_result = session.run(rel_query, node_ids=node_ids)
                relationships = [record.data() for record in relationships_result]
                
                return nodes, relationships

        except Exception as e:
            st.error(f"Error getting single node neighborhood: {str(e)}")
            return [], []

    def search_nodes_in_current_graph(self, search_term, max_results=20):
        """Search for nodes in current graph by name - UPDATED to use NAME"""
        if not self.driver or not search_term:
            return []

        try:
            with self.driver.session(database=self.database) as session:
                search_query = """
                MATCH (n)
                WHERE (
                    any(item IN n.NAME WHERE toLower(toString(item)) CONTAINS toLower($search_term))
                )
                RETURN elementId(n) as node_id,
                       labels(n) as labels,
                       n.NAME as NAME,
                       n.source as source
                LIMIT $max_results
                """
                
                result = session.run(search_query, search_term=search_term, max_results=max_results)
                return [record.data() for record in result]

        except Exception as e:
            st.error(f"Error searching nodes: {str(e)}")
            return []
        

    def get_new_data_only(self, new_data_source_label, limit=500):
        """Get only nodes and relationships that are from new data source"""
        if not self.driver:
            return [], []

        try:
            with self.driver.session(database=self.database) as session:
                # Get new nodes - UPDATED to use NAME
                new_nodes_query = f"""
                MATCH (n)
                WHERE (
                    (n.source IS NOT NULL AND $source IN n.source) OR
                    (n.source = $source)
                )
                RETURN elementId(n) as node_id, 
                    labels(n) as labels,
                    coalesce(n.NAME, n.title, 'Node_' + toString(elementId(n))) as name,
                    n.source as source
                LIMIT {limit}
                """
                
                nodes_result = session.run(new_nodes_query, source=new_data_source_label)
                new_nodes = [record.data() for record in nodes_result]
                
                if not new_nodes:
                    return [], []
                
                node_ids = [node['node_id'] for node in new_nodes]
                
                # Get relationships between new nodes or involving new nodes
                new_rels_query = """
                MATCH (a)-[r]->(b)
                WHERE (
                    elementId(a) IN $node_ids OR elementId(b) IN $node_ids
                ) AND (
                    (r.source IS NOT NULL AND $source IN r.source) OR
                    (r.source = $source)
                )
                RETURN elementId(a) as source_id, elementId(b) as target_id, 
                    type(r) as rel_type,
                    r.source as rel_source
                """
                
                relationships_result = session.run(new_rels_query, node_ids=node_ids, source=new_data_source_label)
                new_relationships = [record.data() for record in relationships_result]
                
                return new_nodes, new_relationships
            
        except Exception as e:
            st.error(f"Error getting new data: {str(e)}")
            return [], []

    def get_node_neighborhood_from_data(self, target_node_name, nodes_data, relationships_data, hops=2, max_nodes=500):
        """Memory-optimized neighborhood extraction from snapshot data - UPDATED to use NAME"""
        if not target_node_name or not nodes_data:
            return [], []

        # Find target nodes (limit search)
        target_node_list = []
        target_name_lower = target_node_name.lower()
        
        for node in nodes_data[:1000]:  # Limit initial search
            # UPDATED: Check both 'name' (from old snapshots) and 'NAME' (from current data)
            name = node.get('name', node.get('NAME', ''))
            if isinstance(name, str) and target_name_lower in name.lower():
                target_node_list.append(node)
                if len(target_node_list) >= 5:  # Limit target nodes
                    break
            elif isinstance(name, list):
                for item in name:
                    if isinstance(item, str) and target_name_lower in item.lower():
                        target_node_list.append(node)
                        break

        if not target_node_list:
            return [], []

        initial_target_ids = {node['node_id'] for node in target_node_list}
        neighborhood_node_ids = set(initial_target_ids)
        current_frontier = set(initial_target_ids)

        # Limit relationship processing
        limited_relationships = relationships_data[:10000]  # Process max 10k relationships

        for _ in range(hops):
            if len(neighborhood_node_ids) > max_nodes:
                break
                
            next_frontier = set()
            for rel in limited_relationships:
                src_id, tgt_id = rel['source_id'], rel['target_id']
                
                if src_id in current_frontier or tgt_id in current_frontier:
                    if src_id not in neighborhood_node_ids:
                        next_frontier.add(src_id)
                        neighborhood_node_ids.add(src_id)
                    if tgt_id not in neighborhood_node_ids:
                        next_frontier.add(tgt_id)
                        neighborhood_node_ids.add(tgt_id)
            
            if not next_frontier or len(neighborhood_node_ids) > max_nodes:
                break
            current_frontier = next_frontier

        # Filter results
        final_nodes = [node for node in nodes_data if node['node_id'] in neighborhood_node_ids]
        final_rels = [rel for rel in limited_relationships 
                     if rel['source_id'] in neighborhood_node_ids and rel['target_id'] in neighborhood_node_ids]

        return final_nodes[:max_nodes], final_rels[:2000]  # Limit final results


def create_focused_node_graph(nodes, relationships, title="Node Focus", target_node_name="", new_data_source_label='pubtator_extraction'):
    """Create a focused graph visualization for single node analysis with enhanced labeling"""
    if not nodes:
        fig = go.Figure()
        fig.add_annotation(text="No data to display", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title=title, height=400)
        return fig

    try:
        G = nx.Graph()
        node_map = {node['node_id']: node for node in nodes}

        # Enhanced color mapping for your specific node labels
        type_colors = {
            'DISEASE': '#FF6B6B',        # Red
            'DRUG': '#4ECDC4',           # Teal  
            'GENETIC_DISORDER': '#9B59B6',  # Purple
            'Gene': '#45B7D1',           # Blue
            'PATHWAYS': '#F39C12',       # Orange
            'PROTEIN': '#2ECC71',        # Green
            'Unknown': '#95A5A6'         # Gray
        }
        
        # Special highlighting colors
        special_colors = {
            'target': '#FFD700',        # Gold for target node
            'target_new': '#FF1493'     # Deep pink for target if it's new
        }

        # Updated color mapping for YOUR actual relationship types
        relationship_colors = {
            'RELATED_GENETIC_DISORDER': '#FF1493',      # Deep Pink
            'COMPLEX_IN_PATHWAY': '#FF6347',            # Tomato Red
            'PROTEIN_DISEASE_ASSOCIATION': '#FF4500',   # Orange Red
            'DDI': '#9932CC',                           # Dark Orchid
            'DRUG_PATHWAY_ASSOCIATION': '#FFD700',      # Gold
            'PPI': '#32CD32',                           # Lime Green
            'DISEASE_PATHWAY_ASSOCIATION': '#FF69B4',   # Hot Pink
            'DRUG_TARGET': '#8A2BE2',                   # Blue Violet
            'DRUG_CARRIER': '#00CED1',                  # Dark Turquoise
            'DRUG_ENZYME': '#FF8C00',                   # Dark Orange
            'DRUG_TRANSPORTER': '#20B2AA',              # Light Sea Green
            'DISEASE_GENETIC_DISORDER': '#DC143C',      # Crimson
            'DRUG_DISEASE_ASSOCIATION': '#1E90FF',      # Dodger Blue
            'PROTEIN_PATHWAY_ASSOCIATION': '#228B22',   # Forest Green
            'COMPLEX_TOP_LEVEL_PATHWAY': '#B22222',     # Fire Brick
            'DPI': '#4B0082',                           # Indigo
            'DEFAULT_NEW_RELATION': '#FF1493'           # Fallback color
        }

        # Add nodes
        for node_id, node_data in node_map.items():
            G.add_node(node_id)

        # Add edges
        for rel in relationships:
            src, tgt = rel['source_id'], rel['target_id']
            if src in node_map and tgt in node_map:
                G.add_edge(src, tgt, rel_data=rel)

        if not G.nodes():
            return create_focused_node_graph([], [], title)

        # Use a more focused layout for smaller graphs
        if len(G.nodes()) <= 20:
            pos = nx.spring_layout(G, k=2, iterations=100, seed=42)
        else:
            pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)

        # Identify different node categories
        target_nodes = set()
        new_nodes = set()
        
        target_name_lower = target_node_name.lower()
        
        for node_id, node_data in node_map.items():
            # UPDATED: Check both 'name' and 'NAME' for compatibility
            name = node_data.get('name', node_data.get('NAME', ''))
            source = node_data.get('source', [])
            
            # Check if this is the target node
            is_target = False
            if isinstance(name, str) and target_name_lower in name.lower():
                is_target = True
            elif isinstance(name, list):
                for item in name:
                    if isinstance(item, str) and target_name_lower in item.lower():
                        is_target = True
                        break
            
            if is_target:
                target_nodes.add(node_id)
            
            # Check if this is new data
            if isinstance(source, list) and new_data_source_label in source:
                new_nodes.add(node_id)
            elif source == new_data_source_label:
                new_nodes.add(node_id)

        # Determine if this is an "After" visualization (has new data)
        is_after_view = len(new_nodes) > 0 or "Current" in title or "After" in title

        # Track what relationship types are actually present for dynamic legend
        present_node_types = set()
        present_new_rel_types = set()

        # Create edge traces with different colors for different relationship types
        edge_traces = []
        
        # Regular edges
        regular_edge_x, regular_edge_y = [], []
        regular_edge_hover = []
        
        # Dictionary to store new relationship traces by type
        new_rel_traces = {}
        
        for edge in G.edges(data=True):
            if edge[0] in pos and edge[1] in pos:
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                
                rel_data = edge[2].get('rel_data', {})
                rel_source = rel_data.get('rel_source', [])
                rel_type = rel_data.get('rel_type', 'RELATIONSHIP')
                
                # Get source and target node names for hover - UPDATED to use both name/NAME
                source_name = node_map[edge[0]].get('name', node_map[edge[0]].get('NAME', 'Unknown'))
                target_name = node_map[edge[1]].get('name', node_map[edge[1]].get('NAME', 'Unknown'))
                
                if isinstance(source_name, list) and source_name:
                    source_name = source_name[0]
                if isinstance(target_name, list) and target_name:
                    target_name = target_name[0]
                
                # Check if this is a new relationship
                is_new_rel = False
                if isinstance(rel_source, list) and new_data_source_label in rel_source:
                    is_new_rel = True
                elif rel_source == new_data_source_label:
                    is_new_rel = True
                
                # Create hover text
                hover_text = f"<b>{rel_type}</b><br>"
                hover_text += f"{source_name} ↔ {target_name}"
                if is_new_rel:
                    hover_text += "<br><b>🆕 NEW RELATIONSHIP</b>"
                
                if is_new_rel and is_after_view:
                    # Track this relationship type for legend
                    present_new_rel_types.add(rel_type)
                    
                    # Get color for this relationship type
                    rel_color = relationship_colors.get(rel_type, relationship_colors['DEFAULT_NEW_RELATION'])
                    
                    # Create or add to trace for this relationship type
                    if rel_type not in new_rel_traces:
                        new_rel_traces[rel_type] = {
                            'x': [], 'y': [], 'hover': [], 'color': rel_color
                        }
                    
                    new_rel_traces[rel_type]['x'].extend([x0, x1, None])
                    new_rel_traces[rel_type]['y'].extend([y0, y1, None])
                    new_rel_traces[rel_type]['hover'].extend([hover_text, hover_text, None])
                else:
                    regular_edge_x.extend([x0, x1, None])
                    regular_edge_y.extend([y0, y1, None])
                    regular_edge_hover.extend([hover_text, hover_text, None])

        # Add regular edges
        if regular_edge_x:
            edge_traces.append(go.Scatter(
                x=regular_edge_x, y=regular_edge_y,
                line=dict(width=2, color='rgba(150,150,150,0.6)'),
                hoverinfo='text', hovertext=regular_edge_hover,
                mode='lines', showlegend=False,
                name="Existing Relationships"
            ))

        # Add new relationship traces (each type gets its own color)
        for rel_type, trace_data in new_rel_traces.items():
            edge_traces.append(go.Scatter(
                x=trace_data['x'], y=trace_data['y'],
                line=dict(width=4, color=trace_data['color'], dash='dot'),
                hoverinfo='text', hovertext=trace_data['hover'],
                mode='lines', showlegend=False,  # Disable plotly legend, we'll use annotation
                name=f"🆕 {rel_type}",
                legendgroup="new_relationships"
            ))

        # Create node traces organized by type and category
        node_traces = []
        
        # Process nodes by their primary label type
        for node_id in G.nodes():
            if node_id not in pos:
                continue
                
            node_data = node_map[node_id]
            labels = node_data.get('labels', [])
            primary_label = labels[0] if labels else 'Unknown'
            
            # Track present node types for legend
            present_node_types.add(primary_label)
            
            # Determine if this node is target or new
            is_target = node_id in target_nodes
            is_new = node_id in new_nodes
            
            # Get position
            x, y = pos[node_id]
            
            # Get display name - UPDATED to use both name/NAME
            name = node_data.get('name', node_data.get('NAME', f'Node_{node_id}'))
            if isinstance(name, list) and name:
                display_name = str(name[0])[:20]  # Longer names for new nodes
            else:
                display_name = str(name)[:20]
            
            # Enhanced hover info (WITHOUT element ID)
            source = node_data.get('source', 'Unknown')
            hover_text = f"<b>{display_name}</b><br>"
            hover_text += f"Type: {primary_label}<br>"
            hover_text += f"Source: {source}"
            
            if is_new:
                hover_text += "<br><b>🆕 NEW NODE</b>"
            if is_target:
                hover_text += "<br><b>🎯 TARGET NODE</b>"
            
            # Determine color and size
            if is_target:
                if is_new:
                    color = special_colors['target_new']
                else:
                    color = special_colors['target']
                size = 35
                show_text = True
            elif is_new:
                color = type_colors.get(primary_label, type_colors['Unknown'])
                size = 25
                show_text = True  # Show labels for new nodes
            else:
                color = type_colors.get(primary_label, type_colors['Unknown'])
                size = 18
                show_text = False  # Don't show labels for existing nodes to reduce clutter
            
            # Create individual node trace (no legend)
            text_mode = 'markers+text' if show_text else 'markers'
            node_traces.append(go.Scatter(
                x=[x], y=[y],
                mode=text_mode,
                hoverinfo='text', hovertext=[hover_text],
                text=[display_name if show_text else ""], 
                textposition="bottom center",
                textfont=dict(size=12, color='black'),
                marker=dict(size=[size], color=[color], line=dict(width=2, color='black'), opacity=0.9),
                showlegend=False  # No plotly legend for nodes
            ))

        # Combine all traces
        all_traces = edge_traces + node_traces

        fig = go.Figure(data=all_traces)
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=16)),
            showlegend=False,  # Disable plotly legend completely
            hovermode='closest',
            margin=dict(b=40, l=5, r=240, t=60),  # Increased right margin for wider legend
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=700,
            plot_bgcolor='white'
        )

        # Create merged legend text - keep original relationship names
        legend_text = "<b>Node labels:</b><br>"
        
        # Only show node types that are actually present
        for node_type in sorted(present_node_types):
            if node_type in type_colors:
                legend_text += f"<span style='color:{type_colors[node_type]}; font-size:12px'>●</span> {node_type}<br>"
        
        # Always show target color if we have a target
        if target_nodes:
            legend_text += f"<span style='color:{special_colors['target']}; font-size:12px'>●</span> Target<br>"
        
        legend_text += "<br><b>📏 Lines:</b><br>"
        legend_text += "<span style='color:rgba(150,150,150,0.6)'>━━</span> Existing<br>"
        
        # Add new relationship colors in "After" view - NO ABBREVIATIONS
        if is_after_view and present_new_rel_types:
            legend_text += "<br><b>🆕 New Relations:</b><br>"
            for rel_type in sorted(present_new_rel_types):
                rel_color = relationship_colors.get(rel_type, relationship_colors['DEFAULT_NEW_RELATION'])
                
                # Keep original relationship name - NO CHANGES
                display_name = rel_type
                
                # Only truncate if extremely long (over 25 characters)
                if len(display_name) > 25:
                    display_name = display_name[:22] + "..."
                
                legend_text += f"<span style='color:{rel_color}; font-size:11px'>┅┅</span> {display_name}<br>"
        
        # Add single merged legend annotation on the right
        fig.add_annotation(
            text=legend_text,
            xref="paper", yref="paper",
            x=1.02, y=1,  # Right side, top
            xanchor="left", yanchor="top",
            showarrow=False,
            align="left",
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(0,0,0,0.3)",
            borderwidth=1,
            font=dict(size=9, color="black"),  # Smaller font to fit longer names
            width=220  # Increased width for full relationship names
        )

        # Cleanup
        del G, node_map
        gc.collect()

        return fig

    except Exception as e:
        st.error(f"Error creating focused graph: {str(e)}")
        return go.Figure()


def create_network_graph_optimized(nodes, relationships, title="Knowledge Graph", highlight_new=False, new_data_source_label='pubtator_extraction', max_nodes=300, max_edges=1000):
    """Memory-optimized graph creation - UPDATED to use NAME"""
    if not nodes:
        fig = go.Figure()
        fig.add_annotation(text="No data to display", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title=title, height=400)
        return fig

    try:
        # Limit data for visualization
        limited_nodes = nodes[:max_nodes]
        limited_relationships = relationships[:max_edges]
        
        G = nx.Graph()
        node_map = {node['node_id']: node for node in limited_nodes}

        # Simplified color mapping
        type_colors = {
            'DISEASE': '#FF6B6B',        # Red
            'DRUG': '#4ECDC4',           # Teal  
            'GENETIC_DISORDER': '#9B59B6',  # Purple
            'Gene': '#45B7D1',           # Blue
            'PATHWAYS': '#F39C12',       # Orange
            'PROTEIN': '#2ECC71',        # Green
            'Unknown': '#95A5A6'         # Gray
        }
        default_color = '#CCCCCC'

        # Add nodes with minimal processing
        for node_id, node_data in node_map.items():
            G.add_node(node_id)

        # Add edges with filtering
        valid_edges = []
        for rel in limited_relationships:
            src, tgt = rel['source_id'], rel['target_id']
            if src in node_map and tgt in node_map:
                G.add_edge(src, tgt)
                valid_edges.append(rel)

        if not G.nodes():
            return create_network_graph_optimized([], [], title)

        # Optimized layout
        if len(G.nodes()) > 100:
            pos = nx.spring_layout(G, k=1, iterations=20, seed=42)  # Reduced iterations
        else:
            pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)

        # Create visualization traces efficiently
        edge_traces = []
        
        # Single edge trace for performance
        edge_x, edge_y = [], []
        for edge in G.edges():
            if edge[0] in pos and edge[1] in pos:
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1, color='rgba(150,150,150,0.6)'),
            hoverinfo='none', mode='lines', showlegend=False
        )

        # Optimized node trace - UPDATED to use NAME
        node_x, node_y, node_colors, node_text, node_hover = [], [], [], [], []
        
        for node_id in G.nodes():
            if node_id in pos:
                x, y = pos[node_id]
                node_x.append(x)
                node_y.append(y)
                
                node_data = node_map[node_id]
                # UPDATED: Check both 'name' and 'NAME'
                name = str(node_data.get('name', node_data.get('NAME', f'Node_{node_id}')))[:15]
                node_text.append(name)
                
                # Simplified coloring
                if highlight_new and node_data.get('source') == new_data_source_label:
                    node_colors.append('#FFD700')
                else:
                    labels = node_data.get('labels', [])
                    color = type_colors.get(labels[0] if labels else 'Default', default_color)
                    node_colors.append(color)
                
                node_hover.append(f"{name}<br>ID: {node_id}")

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text', hovertext=node_hover,
            text=node_text, textposition="bottom center",
            marker=dict(size=15, color=node_colors, line=dict(width=1, color='black'), opacity=0.8),
            showlegend=False
        )

        fig = go.Figure(data=[edge_trace, node_trace])
        fig.update_layout(
            title=dict(text=title, x=0.5),
            showlegend=False, hovermode='closest',
            margin=dict(b=10, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600, plot_bgcolor='white'
        )

        # Force cleanup
        del G, node_map, limited_nodes, limited_relationships
        gc.collect()

        return fig

    except Exception as e:
        st.error(f"Error creating graph: {str(e)}")
        return go.Figure()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_graph_data(limit):
    """Cached data retrieval"""
    if 'visualizer' in st.session_state:
        return st.session_state.visualizer.get_graph_data_lightweight(limit=limit)
    return [], []


def main():
    st.set_page_config(
        page_title="Knowledge Graph Visualizer",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("🔗 Knowledge Graph: Evolution & Analysis")
    st.markdown("Memory-optimized visualization for large graphs")

    # Initialize with connection pooling
    if 'visualizer' not in st.session_state:
        st.session_state.visualizer = GraphVisualizer(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DATABASE_NAME)

    visualizer = st.session_state.visualizer
    new_data_label = "pubtator_extraction"

    # Sidebar with memory-conscious limits
    st.sidebar.header("📸 Snapshot Management")
    snapshot_name_input = st.sidebar.text_input("Snapshot Name", key="snapshot_name_in")
    
    col1_snap, col2_snap = st.sidebar.columns(2)
    with col1_snap:
        if st.button("💾 Save Current State"):
            default_name = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            name = snapshot_name_input if snapshot_name_input else default_name
            if visualizer.save_graph_snapshot(name):
                st.rerun()

    with col2_snap:
        if st.button("🗑️ Clear All Snapshots"):
            if os.path.exists(visualizer.snapshot_dir):
                shutil.rmtree(visualizer.snapshot_dir)
                os.makedirs(visualizer.snapshot_dir, exist_ok=True)
                st.success("Snapshots cleared!")
                st.rerun()

    # Display available snapshots
    snapshots = visualizer.get_available_snapshots()
    if snapshots:
        st.sidebar.subheader("📂 Available Snapshots")
        for snapshot in snapshots[:5]:  # Limit display
            st.sidebar.write(f"• **{snapshot['name']}**")

    st.sidebar.header("🎛️ Options")
    view_mode = st.sidebar.selectbox(
        "View Mode",
        ["🎯 Single Node Focus (Before/After)", "Progression: Before → During → After", "Search & Compare Node Neighborhood", "Full Graph Analysis & Metrics"]
    )
    
    # Reduced default limits for better performance
    node_limit = st.sidebar.slider("Max nodes", 100, 2000, 500, step=100)
    
    if view_mode == "🎯 Single Node Focus (Before/After)":
        st.header("🎯 Single Node Analysis: Before vs After")
        st.markdown("**Compare individual nodes and their neighborhoods before and after data addition**")
        
        # Search for a specific node
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_term = st.text_input(
                "🔍 Search for a node to analyze:", 
                placeholder="Enter node name (e.g., 'clofibrate', 'diabetes')",
                key="node_search"
            )
        
        with col2:
            hops = st.selectbox("Neighborhood depth:", [1, 2, 3], index=0)
        
        if search_term:
            # Show available matching nodes
            matching_nodes = visualizer.search_nodes_in_current_graph(search_term, max_results=10)
            
            if matching_nodes:
                st.subheader("📋 Matching Nodes Found:")
                
                # Create a selection interface
                node_options = []
                for node in matching_nodes:
                    # UPDATED: Check both 'name' and 'NAME'
                    name = node.get('name', node.get('NAME', ['Unknown']))
                    if isinstance(name, list):
                        display_name = name[0] if name else 'Unknown'
                    else:
                        display_name = str(name)
                    
                    labels = ', '.join(node.get('labels', ['Unknown']))
                    source = node.get('source', ['Unknown'])
                    if isinstance(source, list):
                        source_str = ', '.join(source) if source else 'Unknown'
                    else:
                        source_str = str(source)
                    
                    option_text = f"{display_name} [{labels}] (Source: {source_str})"
                    node_options.append((option_text, display_name, node))
                
                selected_option = st.selectbox(
                    "Select a node to analyze:",
                    options=range(len(node_options)),
                    format_func=lambda x: node_options[x][0] if x < len(node_options) else "",
                    key="selected_node"
                )
                
                if selected_option is not None and selected_option < len(node_options):
                    selected_node_name = node_options[selected_option][1]
                    selected_node = node_options[selected_option][2]
                    
                    st.success(f"✅ Analyzing node: **{selected_node_name}**")
                    
                    # Check for available snapshots
                    available_snapshots = visualizer.get_available_snapshots()
                    
                    if not available_snapshots:
                        st.warning("⚠️ No snapshots found. Please create a snapshot first.")
                        if st.button("📸 Save Current State as Snapshot"):
                            if visualizer.save_graph_snapshot("before_analysis"):
                                st.rerun()
                    else:
                        # Select snapshot for comparison
                        snapshot_names = [s['name'] for s in available_snapshots]
                        selected_snapshot = st.selectbox(
                            "Select 'BEFORE' snapshot for comparison:",
                            snapshot_names,
                            key="comparison_snapshot"
                        )
                        
                        if selected_snapshot:
                            # Load before data
                            before_data = visualizer.load_graph_snapshot(selected_snapshot)
                            
                            if before_data:
                                # Get current neighborhood
                                st.info(f"🔄 Loading current neighborhood for: {selected_node_name}")
                                current_nodes, current_rels = visualizer.get_single_node_neighborhood(
                                    selected_node_name, hops=hops, max_neighbors=50
                                )
                                
                                # Get before neighborhood
                                st.info(f"🔄 Loading before neighborhood from snapshot: {selected_snapshot}")
                                before_nodes, before_rels = visualizer.get_node_neighborhood_from_data(
                                    selected_node_name, 
                                    before_data['nodes'], 
                                    before_data['relationships'], 
                                    hops=hops, 
                                    max_nodes=50
                                )
                                
                                # Display comparison
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.subheader(f"📊 BEFORE ({selected_snapshot})")
                                    
                                    if before_nodes:
                                        before_fig = create_focused_node_graph(
                                            before_nodes, 
                                            before_rels,
                                            f"Before: {selected_node_name}",
                                            target_node_name=selected_node_name,
                                            new_data_source_label=new_data_label
                                        )
                                        st.plotly_chart(before_fig, use_container_width=True, key=f"before_focus_{selected_node_name}")
                                        
                                        # Before metrics
                                        st.metrics_container = st.container()
                                        with st.metrics_container:
                                            col1_1, col1_2 = st.columns(2)
                                            col1_1.metric("Nodes", len(before_nodes))
                                            col1_2.metric("Relationships", len(before_rels))
                                    else:
                                        st.info(f"Node '{selected_node_name}' not found in the selected snapshot")
                                
                                with col2:
                                    st.subheader("📈 AFTER (Current)")
                                    
                                    if current_nodes:
                                        after_fig = create_focused_node_graph(
                                            current_nodes, 
                                            current_rels,
                                            f"Current: {selected_node_name}",
                                            target_node_name=selected_node_name,
                                            new_data_source_label=new_data_label
                                        )
                                        st.plotly_chart(after_fig, use_container_width=True, key=f"after_focus_{selected_node_name}")
                                        
                                        # After metrics
                                        st.metrics_container2 = st.container()
                                        with st.metrics_container2:
                                            col2_1, col2_2 = st.columns(2)
                                            col2_1.metric("Nodes", len(current_nodes))
                                            col2_2.metric("Relationships", len(current_rels))
                                    else:
                                        st.warning(f"Node '{selected_node_name}' not found in current graph")
                                
                                # Summary of changes
                                if before_nodes and current_nodes:
                                    st.subheader("📊 Change Summary")
                                    
                                    # Calculate differences
                                    before_node_count = len(before_nodes)
                                    current_node_count = len(current_nodes)
                                    before_rel_count = len(before_rels)
                                    current_rel_count = len(current_rels)
                                    
                                    # Count new data
                                    new_nodes_count = 0
                                    new_rels_count = 0
                                    
                                    for node in current_nodes:
                                        source = node.get('source', [])
                                        if isinstance(source, list) and new_data_label in source:
                                            new_nodes_count += 1
                                        elif source == new_data_label:
                                            new_nodes_count += 1
                                    
                                    for rel in current_rels:
                                        rel_source = rel.get('rel_source', [])
                                        if isinstance(rel_source, list) and new_data_label in rel_source:
                                            new_rels_count += 1
                                        elif rel_source == new_data_label:
                                            new_rels_count += 1
                                    
                                    # Display change metrics
                                    col1, col2, col3, col4 = st.columns(4)
                                    col1.metric("Node Change", current_node_count, current_node_count - before_node_count)
                                    col2.metric("Relationship Change", current_rel_count, current_rel_count - before_rel_count)
                                    col3.metric("New Nodes Added", new_nodes_count)
                                    col4.metric("New Relationships", new_rels_count)
                                    
                                    # Legend
                                    st.markdown("""
                                    **Legend:**
                                    - 🟡 **Gold**: Target node being analyzed
                                    - 🔴 **Deep Pink**: New nodes from data extraction  
                                    - 🩷 **Hot Pink**: Existing nodes connected to new data
                                    - **Dotted lines**: New relationships added
                                    - **Solid lines**: Existing relationships
                                    """)
                            else:
                                st.error("Failed to load snapshot data")
            else:
                st.info("No matching nodes found. Try a different search term.")
    
    elif view_mode == "Progression: Before → During → After":
        st.header("📈 Graph Evolution")

        available_snapshots = visualizer.get_available_snapshots()
        if not available_snapshots:
            st.warning("⚠️ No snapshots found.")
            if st.button("📸 Save Current State"):
                if visualizer.save_graph_snapshot("initial_snapshot"):
                    st.rerun()
        else:
            snapshot_names = [s['name'] for s in available_snapshots]
            selected_snapshot = st.selectbox("Select 'BEFORE' snapshot:", snapshot_names)

            before_data = visualizer.load_graph_snapshot(selected_snapshot)

            if before_data:
                # Use cached data retrieval
                current_nodes, current_rels = get_cached_graph_data(node_limit)
                new_nodes, new_rels = visualizer.get_new_data_only(new_data_label, limit=node_limit//2)

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.subheader(f"📊 BEFORE")
                    before_fig = create_network_graph_optimized(
                        before_data['nodes'][:node_limit//3], 
                        before_data['relationships'][:1000],
                        f"Before: {selected_snapshot}"
                    )
                    st.plotly_chart(before_fig, use_container_width=True, key=f"before_{selected_snapshot}")
                    st.metric("Nodes", min(len(before_data['nodes']), node_limit//3))

                with col2:
                    st.subheader(f"🆕 NEW Data")
                    if new_nodes:
                        new_fig = create_network_graph_optimized(
                            new_nodes[:node_limit//3], new_rels[:500],
                            "New Data", highlight_new=True, new_data_source_label=new_data_label
                        )
                        st.plotly_chart(new_fig, use_container_width=True, key=f"new_{selected_snapshot}")
                    else:
                        st.info("No new data found")
                    st.metric("New Nodes", len(new_nodes))

                with col3:
                    st.subheader("📈 AFTER")
                    after_fig = create_network_graph_optimized(
                        current_nodes, current_rels,
                        "Current State", highlight_new=True, new_data_source_label=new_data_label
                    )
                    st.plotly_chart(after_fig, use_container_width=True, key=f"after_{selected_snapshot}")
                    st.metric("Total Nodes", len(current_nodes))

    elif view_mode == "Search & Compare Node Neighborhood":
        st.header("🔍 Node Neighborhood Comparison")
        search_term = st.text_input("Search for a node:", placeholder="Enter node name...")
        hops = st.slider("Neighborhood depth", 1, 3, 1)

        if search_term and visualizer.get_available_snapshots():
            current_nodes, current_rels = get_cached_graph_data(node_limit)
            snapshots = visualizer.get_available_snapshots()
            selected_snapshot = st.selectbox("Select snapshot:", [s['name'] for s in snapshots])
            before_data = visualizer.load_graph_snapshot(selected_snapshot)

            if before_data:
                before_neighborhood = visualizer.get_node_neighborhood_from_data(
                    search_term, before_data['nodes'], before_data['relationships'], hops, max_nodes=200
                )
                current_neighborhood = visualizer.get_node_neighborhood_from_data(
                    search_term, current_nodes, current_rels, hops, max_nodes=200
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("BEFORE")
                    if before_neighborhood[0]:
                        before_fig = create_network_graph_optimized(
                            before_neighborhood[0], before_neighborhood[1],
                            f"Before: {search_term}", max_nodes=150, max_edges=300
                        )
                        st.plotly_chart(before_fig, use_container_width=True, key=f"search_before_{search_term}")

                with col2:
                    st.subheader("AFTER")
                    if current_neighborhood[0]:
                        after_fig = create_network_graph_optimized(
                            current_neighborhood[0], current_neighborhood[1],
                            f"After: {search_term}", highlight_new=True, new_data_source_label=new_data_label,
                            max_nodes=150, max_edges=300
                        )
                        st.plotly_chart(after_fig, use_container_width=True, key=f"search_after_{search_term}")

    elif view_mode == "Full Graph Analysis & Metrics":
        st.header("📊 Graph Analysis")
        
        current_nodes, current_rels = get_cached_graph_data(node_limit)
        new_nodes, new_rels = visualizer.get_new_data_only(new_data_label, limit=node_limit//2)

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Nodes", len(current_nodes))
        col2.metric("Total Relationships", len(current_rels))
        col3.metric("New Nodes", len(new_nodes))
        col4.metric("New Relationships", len(new_rels))

        # Visualization
        if current_nodes:
            full_fig = create_network_graph_optimized(
                current_nodes, current_rels,
                "Full Graph Analysis", highlight_new=True, new_data_source_label=new_data_label
            )
            st.plotly_chart(full_fig, use_container_width=True, key="full_analysis")

        # Type distribution
        if current_nodes:
            st.subheader("📊 Node Type Distribution")
            type_counts = {}
            for node in current_nodes:
                labels = node.get('labels', ['Unknown'])
                label = labels[0] if labels else 'Unknown'
                type_counts[label] = type_counts.get(label, 0) + 1
            
            if type_counts:
                df = pd.DataFrame(list(type_counts.items()), columns=['Type', 'Count'])
                fig = px.bar(df, x='Type', y='Count', title="Node Types")
                st.plotly_chart(fig, use_container_width=True, key="type_dist")

    # Force garbage collection periodically
    if st.sidebar.button("🧹 Force Memory Cleanup"):
        gc.collect()
        st.success("Memory cleanup performed")


if __name__ == "__main__":
    main()
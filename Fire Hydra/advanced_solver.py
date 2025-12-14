"""
Advanced Solver Options

Hardy-Cross iteratif çözücü ve solver karşılaştırma:
- Hardy-Cross method
- Convergence kriterleri
- Solver comparison (Hazen-Williams vs Hardy-Cross)
- Performance metrics
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import time
import math


@dataclass
class SolverSettings:
    """Solver ayarları"""
    method: str = "hazen_williams"  # hazen_williams, hardy_cross
    max_iterations: int = 100
    tolerance: float = 0.001  # Yakınsama toleransı
    relaxation_factor: float = 1.0  # Hardy-Cross için
    
    
@dataclass
class SolverResult:
    """Solver sonucu"""
    success: bool
    iterations: int
    convergence_error: float
    solve_time: float  # saniye
    method: str
    node_pressures: Dict[str, float] = None
    pipe_flows: Dict[str, float] = None
    
    def __post_init__(self):
        if self.node_pressures is None:
            self.node_pressures = {}
        if self.pipe_flows is None:
            self.pipe_flows = {}


class HardyCrossSolver:
    """
    Hardy-Cross iteratif çözücü
    
    Loop bazlı akış dağılımı hesabı
    """
    
    def __init__(self, network, settings: SolverSettings):
        self.network = network
        self.settings = settings
        
    def solve(self) -> SolverResult:
        """Hardy-Cross metodu ile çöz"""
        start_time = time.time()
        
        # Loop'ları tespit et
        loops = self._find_loops()
        
        if not loops:
            # Loop yoksa basit çözüm
            return self._solve_simple()
        
        # Başlangıç akış tahminleri
        pipe_flows = self._initialize_flows()
        
        # Iterasyon
        for iteration in range(self.settings.max_iterations):
            max_correction = 0.0
            
            # Her loop için akış düzeltmesi
            for loop in loops:
                correction = self._calculate_loop_correction(loop, pipe_flows)
                
                # Akışları düzelt
                for pipe_id in loop:
                    pipe_flows[pipe_id] += correction * self.settings.relaxation_factor
                
                max_correction = max(max_correction, abs(correction))
            
            # Yakınsama kontrolü
            if max_correction < self.settings.tolerance:
                # Basınçları hesapla
                node_pressures = self._calculate_pressures(pipe_flows)
                
                solve_time = time.time() - start_time
                
                return SolverResult(
                    success=True,
                    iterations=iteration + 1,
                    convergence_error=max_correction,
                    solve_time=solve_time,
                    method="hardy_cross",
                    node_pressures=node_pressures,
                    pipe_flows=pipe_flows
                )
        
        # Yakınsamadı
        solve_time = time.time() - start_time
        return SolverResult(
            success=False,
            iterations=self.settings.max_iterations,
            convergence_error=max_correction,
            solve_time=solve_time,
            method="hardy_cross"
        )
    
    def _find_loops(self) -> List[List[str]]:
        """Network'teki loop'ları tespit et (basit algoritma)"""
        # Basit loop tespiti - gerçek uygulamada DFS kullanılır
        loops = []
        
        # Her pipe için kontrol et
        visited_pipes = set()
        
        for pipe in self.network.pipes:
            if pipe.id in visited_pipes:
                continue
                
            # Bu pipe'dan başlayarak loop ara
            loop = self._trace_loop(pipe.id, visited_pipes)
            if loop and len(loop) >= 3:
                loops.append(loop)
                visited_pipes.update(loop)
        
        return loops
    
    def _trace_loop(self, start_pipe_id: str, visited: set) -> Optional[List[str]]:
        """Bir pipe'dan başlayarak loop'u takip et"""
        # Basitleştirilmiş - gerçekte graph traversal
        loop = [start_pipe_id]
        
        current_pipe = next((p for p in self.network.pipes if p.id == start_pipe_id), None)
        if not current_pipe:
            return None
        
        # En fazla 10 pipe takip et
        for _ in range(10):
            # Bu pipe'a bağlı diğer pipe'ları bul
            connected = self._find_connected_pipes(current_pipe.node2_id, exclude=loop)
            
            if not connected:
                break
            
            next_pipe = connected[0]
            if next_pipe.id == start_pipe_id:
                # Loop kapandı
                return loop
            
            loop.append(next_pipe.id)
            current_pipe = next_pipe
        
        return None if len(loop) < 3 else loop
    
    def _find_connected_pipes(self, node_id: str, exclude: List[str]) -> List:
        """Bir node'a bağlı pipe'ları bul"""
        connected = []
        for pipe in self.network.pipes:
            if pipe.id in exclude:
                continue
            if pipe.node1_id == node_id or pipe.node2_id == node_id:
                connected.append(pipe)
        return connected
    
    def _initialize_flows(self) -> Dict[str, float]:
        """Başlangıç akış tahminleri"""
        flows = {}
        
        # Eşit dağılım varsayımı
        total_demand = sum(getattr(node, 'flow_rate', 80.0) 
                          for node in self.network.nodes.values() 
                          if node.node_type.value == 'sprinkler')
        
        if len(self.network.pipes) > 0:
            avg_flow = total_demand / len(self.network.pipes)
        else:
            avg_flow = 0
        
        for pipe in self.network.pipes:
            flows[pipe.id] = avg_flow
        
        return flows
    
    def _calculate_loop_correction(self, loop: List[str], flows: Dict[str, float]) -> float:
        """Loop için akış düzeltmesi hesapla"""
        sum_hf = 0.0
        sum_dhf = 0.0
        
        for pipe_id in loop:
            pipe = next((p for p in self.network.pipes if p.id == pipe_id), None)
            if not pipe:
                continue
            
            Q = flows.get(pipe_id, 0.0)
            
            # Hazen-Williams head loss
            # hf = K * Q^1.852
            K = 10.67 * pipe.length / ((100 ** 1.852) * (pipe.diameter ** 4.87))
            
            hf = K * abs(Q) ** 1.852 * (1 if Q >= 0 else -1)
            dhf = 1.852 * K * abs(Q) ** 0.852
            
            sum_hf += hf
            sum_dhf += dhf
        
        if sum_dhf == 0:
            return 0.0
        
        return -sum_hf / sum_dhf
    
    def _calculate_pressures(self, flows: Dict[str, float]) -> Dict[str, float]:
        """Akışlardan basınçları hesapla"""
        pressures = {}
        
        # Kaynak node'dan başla
        source_node = next((n for n in self.network.nodes.values() 
                           if n.node_type.value == 'source'), None)
        
        if source_node:
            pressures[source_node.id] = getattr(source_node, 'pressure', 5.0)
            
            # BFS ile diğer node'ları hesapla
            visited = {source_node.id}
            queue = [source_node.id]
            
            while queue:
                current_id = queue.pop(0)
                current_pressure = pressures[current_id]
                
                # Bağlı pipe'ları bul
                for pipe in self.network.pipes:
                    next_node_id = None
                    
                    if pipe.node1_id == current_id and pipe.node2_id not in visited:
                        next_node_id = pipe.node2_id
                    elif pipe.node2_id == current_id and pipe.node1_id not in visited:
                        next_node_id = pipe.node1_id
                    
                    if next_node_id:
                        # Basınç kaybını hesapla
                        Q = flows.get(pipe.id, 0.0)
                        K = 10.67 * pipe.length / ((100 ** 1.852) * (pipe.diameter ** 4.87))
                        hf = K * abs(Q) ** 1.852
                        
                        # Bar cinsinden
                        hf_bar = hf / 10.2  # m su sütunu -> bar
                        
                        pressures[next_node_id] = current_pressure - hf_bar
                        visited.add(next_node_id)
                        queue.append(next_node_id)
        
        return pressures
    
    def _solve_simple(self) -> SolverResult:
        """Loop olmayan basit network çözümü"""
        start_time = time.time()
        
        # Basit seri hesaplama
        flows = self._initialize_flows()
        pressures = self._calculate_pressures(flows)
        
        solve_time = time.time() - start_time
        
        return SolverResult(
            success=True,
            iterations=1,
            convergence_error=0.0,
            solve_time=solve_time,
            method="hardy_cross_simple",
            node_pressures=pressures,
            pipe_flows=flows
        )


class SolverComparisonDialog(tk.Toplevel):
    """Solver karşılaştırma dialogu"""
    
    def __init__(self, parent, network, db):
        super().__init__(parent)
        
        self.network = network
        self.db = db
        
        self.title("Solver Karşılaştırma")
        self.geometry("800x600")
        
        self._create_widgets()
        
        self.transient(parent)
        self.grab_set()
    
    def _create_widgets(self):
        """Widget'ları oluştur"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Başlık
        ttk.Label(main_frame, text="⚙️ Solver Karşılaştırma", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))
        
        # Ayarlar frame
        settings_frame = ttk.LabelFrame(main_frame, text="Solver Ayarları", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)
        
        # Max iterations
        ttk.Label(settings_frame, text="Max İterasyon:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.max_iter_var = tk.IntVar(value=100)
        ttk.Spinbox(settings_frame, from_=10, to=1000, textvariable=self.max_iter_var, 
                   width=15).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Tolerance
        ttk.Label(settings_frame, text="Tolerans:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.tolerance_var = tk.DoubleVar(value=0.001)
        ttk.Entry(settings_frame, textvariable=self.tolerance_var, width=15).grid(
            row=1, column=1, sticky=tk.W, pady=5)
        
        # Buton frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="🔄 Karşılaştır", 
                  command=self._run_comparison, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Kapat", 
                  command=self.destroy, width=15).pack(side=tk.RIGHT, padx=5)
        
        # Sonuç frame
        result_frame = ttk.LabelFrame(main_frame, text="Karşılaştırma Sonuçları", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Tablo
        columns = ('method', 'success', 'iterations', 'error', 'time')
        self.tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=8)
        
        self.tree.heading('method', text='Metod')
        self.tree.heading('success', text='Başarı')
        self.tree.heading('iterations', text='İterasyon')
        self.tree.heading('error', text='Hata')
        self.tree.heading('time', text='Süre (ms)')
        
        self.tree.column('method', width=150)
        self.tree.column('success', width=80)
        self.tree.column('iterations', width=100)
        self.tree.column('error', width=100)
        self.tree.column('time', width=100)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Detay metin
        detail_frame = ttk.Frame(result_frame)
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        ttk.Label(detail_frame, text="Detaylar:").pack(anchor=tk.W)
        
        self.detail_text = tk.Text(detail_frame, height=8, width=70)
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(detail_frame, command=self.detail_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.detail_text.config(yscrollcommand=scrollbar.set)
    
    def _run_comparison(self):
        """Solver'ları karşılaştır"""
        if not self.network.nodes or not self.network.pipes:
            messagebox.showwarning("Uyarı", "Network boş!")
            return
        
        # Tabloyu temizle
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.detail_text.delete('1.0', tk.END)
        
        # Ayarları al
        settings = SolverSettings(
            max_iterations=self.max_iter_var.get(),
            tolerance=self.tolerance_var.get()
        )
        
        results = []
        
        # 1. Hazen-Williams (basit)
        try:
            from solver import HydraulicSolver
            
            hw_start = time.time()
            hw_solver = HydraulicSolver(self.network, self.db)
            hw_result = hw_solver.solve()
            hw_time = time.time() - hw_start
            
            results.append({
                'method': 'Hazen-Williams (Basit)',
                'success': hw_result.success,
                'iterations': 1,
                'error': 0.0,
                'time': hw_time * 1000
            })
        except Exception as e:
            results.append({
                'method': 'Hazen-Williams (Basit)',
                'success': False,
                'iterations': 0,
                'error': float('inf'),
                'time': 0.0,
                'error_msg': str(e)
            })
        
        # 2. Hardy-Cross
        try:
            hc_solver = HardyCrossSolver(self.network, settings)
            hc_result = hc_solver.solve()
            
            results.append({
                'method': 'Hardy-Cross (İteratif)',
                'success': hc_result.success,
                'iterations': hc_result.iterations,
                'error': hc_result.convergence_error,
                'time': hc_result.solve_time * 1000
            })
        except Exception as e:
            results.append({
                'method': 'Hardy-Cross (İteratif)',
                'success': False,
                'iterations': 0,
                'error': float('inf'),
                'time': 0.0,
                'error_msg': str(e)
            })
        
        # Sonuçları tabloya ekle
        for result in results:
            success_str = "✅ Evet" if result['success'] else "❌ Hayır"
            
            self.tree.insert('', tk.END, values=(
                result['method'],
                success_str,
                result['iterations'],
                f"{result['error']:.6f}",
                f"{result['time']:.2f}"
            ))
        
        # Detayları göster
        detail_lines = []
        detail_lines.append("=" * 60)
        detail_lines.append("SOLVER KARŞILAŞTIRMA RAPORU")
        detail_lines.append("=" * 60)
        detail_lines.append("")
        
        for i, result in enumerate(results, 1):
            detail_lines.append(f"{i}. {result['method']}")
            detail_lines.append(f"   Başarı: {'Evet' if result['success'] else 'Hayır'}")
            detail_lines.append(f"   İterasyon: {result['iterations']}")
            detail_lines.append(f"   Yakınsama Hatası: {result['error']:.6f}")
            detail_lines.append(f"   Hesaplama Süresi: {result['time']:.2f} ms")
            
            if 'error_msg' in result:
                detail_lines.append(f"   Hata: {result['error_msg']}")
            
            detail_lines.append("")
        
        # En hızlısı
        if results:
            fastest = min(results, key=lambda r: r['time'] if r['success'] else float('inf'))
            if fastest['success']:
                detail_lines.append(f"⚡ EN HIZLI: {fastest['method']} ({fastest['time']:.2f} ms)")
        
        self.detail_text.insert('1.0', '\n'.join(detail_lines))


def show_solver_comparison(parent, network, db):
    """Solver karşılaştırma dialogunu aç"""
    dialog = SolverComparisonDialog(parent, network, db)
    parent.wait_window(dialog)

"""
FireHydra - Komut Yönetimi (Undo/Redo)
======================================

Command Pattern kullanarak geri al/yinele işlevselliği.
Her kullanıcı eylemi bir Command objesi olarak kaydedilir.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import copy

from models import Node, Pipe, PipeNetwork, NodeType, Coordinates


class Command(ABC):
    """Soyut Komut Sınıfı"""
    
    @abstractmethod
    def execute(self) -> bool:
        """Komutu çalıştır"""
        pass
    
    @abstractmethod
    def undo(self) -> bool:
        """Komutu geri al"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Komut açıklaması"""
        pass


class CommandManager:
    """
    Komut Yöneticisi
    
    Undo/Redo stack'lerini yönetir.
    """
    
    def __init__(self, max_history: int = 50):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.max_history = max_history
        
        # Değişiklik callback
        self._on_change_callback = None
    
    def set_on_change_callback(self, callback):
        """Değişiklik olduğunda çağrılacak fonksiyon"""
        self._on_change_callback = callback
    
    def execute(self, command: Command) -> bool:
        """Komutu çalıştır ve geçmişe ekle"""
        if command.execute():
            self.undo_stack.append(command)
            self.redo_stack.clear()  # Yeni komut sonrası redo temizlenir
            
            # Maksimum geçmiş kontrolü
            if len(self.undo_stack) > self.max_history:
                self.undo_stack.pop(0)
            
            self._notify_change()
            return True
        return False
    
    def undo(self) -> bool:
        """Son komutu geri al"""
        if not self.can_undo():
            return False
        
        command = self.undo_stack.pop()
        if command.undo():
            self.redo_stack.append(command)
            self._notify_change()
            return True
        else:
            # Geri alma başarısız, komutu geri koy
            self.undo_stack.append(command)
            return False
    
    def redo(self) -> bool:
        """Son geri alınan komutu yinele"""
        if not self.can_redo():
            return False
        
        command = self.redo_stack.pop()
        if command.execute():
            self.undo_stack.append(command)
            self._notify_change()
            return True
        else:
            self.redo_stack.append(command)
            return False
    
    def can_undo(self) -> bool:
        """Geri alma mümkün mü?"""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Yineleme mümkün mü?"""
        return len(self.redo_stack) > 0
    
    def get_undo_description(self) -> str:
        """Son geri alınabilecek komutun açıklaması"""
        if self.undo_stack:
            return self.undo_stack[-1].get_description()
        return ""
    
    def get_redo_description(self) -> str:
        """Son yinelenebilecek komutun açıklaması"""
        if self.redo_stack:
            return self.redo_stack[-1].get_description()
        return ""
    
    def clear(self):
        """Tüm geçmişi temizle"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._notify_change()
    
    def _notify_change(self):
        """Değişiklik bildir"""
        if self._on_change_callback:
            self._on_change_callback()


# ==================== Concrete Commands ====================

class AddNodeCommand(Command):
    """Node ekleme komutu"""
    
    def __init__(self, network: PipeNetwork, node: Node):
        self.network = network
        self.node = node
        self.node_data = None
    
    def execute(self) -> bool:
        try:
            self.network.add_node(self.node)
            return True
        except Exception:
            return False
    
    def undo(self) -> bool:
        try:
            self.network.remove_node(self.node.id)
            return True
        except Exception:
            return False
    
    def get_description(self) -> str:
        return f"Düğüm ekle: {self.node.id}"


class RemoveNodeCommand(Command):
    """Node silme komutu"""
    
    def __init__(self, network: PipeNetwork, node_id: str):
        self.network = network
        self.node_id = node_id
        
        # Silinecek node'u ve bağlı boruları sakla
        self.node_backup: Optional[Node] = None
        self.connected_pipes_backup: List[Pipe] = []
    
    def execute(self) -> bool:
        try:
            # Yedekle
            node = self.network.get_node(self.node_id)
            if not node:
                return False
            
            # Node'u deep copy ile yedekle
            self.node_backup = copy.deepcopy(node)
            
            # Bağlı boruları yedekle
            self.connected_pipes_backup = []
            for pipe in self.network.get_connected_pipes(self.node_id):
                self.connected_pipes_backup.append(copy.deepcopy(pipe))
            
            # Sil
            self.network.remove_node(self.node_id)
            return True
        except Exception:
            return False
    
    def undo(self) -> bool:
        try:
            if not self.node_backup:
                return False
            
            # Node'u geri ekle
            self.network.add_node(self.node_backup)
            
            # Bağlı boruları geri ekle
            for pipe in self.connected_pipes_backup:
                # Diğer uçtaki node var mı kontrol et
                other_id = pipe.end_node_id if pipe.start_node_id == self.node_id else pipe.start_node_id
                if other_id in self.network.nodes:
                    self.network.add_pipe(pipe)
            
            return True
        except Exception:
            return False
    
    def get_description(self) -> str:
        return f"Düğüm sil: {self.node_id}"


class AddPipeCommand(Command):
    """Boru ekleme komutu"""
    
    def __init__(self, network: PipeNetwork, pipe: Pipe):
        self.network = network
        self.pipe = pipe
    
    def execute(self) -> bool:
        try:
            self.network.add_pipe(self.pipe)
            return True
        except Exception:
            return False
    
    def undo(self) -> bool:
        try:
            self.network.remove_pipe(self.pipe.id)
            return True
        except Exception:
            return False
    
    def get_description(self) -> str:
        return f"Boru ekle: {self.pipe.id}"


class RemovePipeCommand(Command):
    """Boru silme komutu"""
    
    def __init__(self, network: PipeNetwork, pipe_id: str):
        self.network = network
        self.pipe_id = pipe_id
        self.pipe_backup: Optional[Pipe] = None
    
    def execute(self) -> bool:
        try:
            pipe = self.network.get_pipe(self.pipe_id)
            if not pipe:
                return False
            
            self.pipe_backup = copy.deepcopy(pipe)
            self.network.remove_pipe(self.pipe_id)
            return True
        except Exception:
            return False
    
    def undo(self) -> bool:
        try:
            if not self.pipe_backup:
                return False
            
            self.network.add_pipe(self.pipe_backup)
            return True
        except Exception:
            return False
    
    def get_description(self) -> str:
        return f"Boru sil: {self.pipe_id}"


class MoveNodeCommand(Command):
    """Node taşıma komutu"""
    
    def __init__(self, network: PipeNetwork, node_id: str, 
                 new_x: float, new_y: float, new_z: Optional[float] = None):
        self.network = network
        self.node_id = node_id
        self.new_x = new_x
        self.new_y = new_y
        self.new_z = new_z
        
        # Eski koordinatlar
        self.old_x: float = 0
        self.old_y: float = 0
        self.old_z: float = 0
    
    def execute(self) -> bool:
        try:
            node = self.network.get_node(self.node_id)
            if not node:
                return False
            
            # Eski değerleri sakla
            self.old_x = node.coordinates.x
            self.old_y = node.coordinates.y
            self.old_z = node.coordinates.z
            
            # Yeni değerleri uygula
            node.coordinates.x = self.new_x
            node.coordinates.y = self.new_y
            if self.new_z is not None:
                node.coordinates.z = self.new_z
            
            # Bağlı boruların uzunluklarını güncelle
            self._update_connected_pipe_lengths(node)
            
            return True
        except Exception:
            return False
    
    def undo(self) -> bool:
        try:
            node = self.network.get_node(self.node_id)
            if not node:
                return False
            
            node.coordinates.x = self.old_x
            node.coordinates.y = self.old_y
            node.coordinates.z = self.old_z
            
            self._update_connected_pipe_lengths(node)
            
            return True
        except Exception:
            return False
    
    def _update_connected_pipe_lengths(self, node: Node):
        """Bağlı boruların uzunluklarını güncelle"""
        for pipe in self.network.get_connected_pipes(node.id):
            start = self.network.get_node(pipe.start_node_id)
            end = self.network.get_node(pipe.end_node_id)
            if start and end:
                # 2D mesafe (mm -> m)
                pipe.length = start.coordinates.distance_2d(end.coordinates) / 1000
                # Kot farkı
                pipe.elevation_change = end.get_elevation() - start.get_elevation()
    
    def get_description(self) -> str:
        return f"Düğüm taşı: {self.node_id}"


class ModifyNodeCommand(Command):
    """Node özelliklerini değiştirme komutu"""
    
    def __init__(self, network: PipeNetwork, node_id: str, 
                 new_properties: Dict[str, Any]):
        self.network = network
        self.node_id = node_id
        self.new_properties = new_properties
        self.old_properties: Dict[str, Any] = {}
    
    def execute(self) -> bool:
        try:
            node = self.network.get_node(self.node_id)
            if not node:
                return False
            
            # Eski değerleri sakla ve yenileri uygula
            for key, value in self.new_properties.items():
                if hasattr(node, key):
                    self.old_properties[key] = getattr(node, key)
                    setattr(node, key, value)
            
            return True
        except Exception:
            return False
    
    def undo(self) -> bool:
        try:
            node = self.network.get_node(self.node_id)
            if not node:
                return False
            
            for key, value in self.old_properties.items():
                setattr(node, key, value)
            
            return True
        except Exception:
            return False
    
    def get_description(self) -> str:
        return f"Düğüm düzenle: {self.node_id}"


class ModifyPipeCommand(Command):
    """Boru özelliklerini değiştirme komutu"""
    
    def __init__(self, network: PipeNetwork, pipe_id: str,
                 new_properties: Dict[str, Any]):
        self.network = network
        self.pipe_id = pipe_id
        self.new_properties = new_properties
        self.old_properties: Dict[str, Any] = {}
    
    def execute(self) -> bool:
        try:
            pipe = self.network.get_pipe(self.pipe_id)
            if not pipe:
                return False
            
            for key, value in self.new_properties.items():
                if hasattr(pipe, key):
                    self.old_properties[key] = getattr(pipe, key)
                    setattr(pipe, key, value)
            
            return True
        except Exception:
            return False
    
    def undo(self) -> bool:
        try:
            pipe = self.network.get_pipe(self.pipe_id)
            if not pipe:
                return False
            
            for key, value in self.old_properties.items():
                setattr(pipe, key, value)
            
            return True
        except Exception:
            return False
    
    def get_description(self) -> str:
        return f"Boru düzenle: {self.pipe_id}"


class CompoundCommand(Command):
    """Birden fazla komutu gruplayarak tek undo/redo yapma"""
    
    def __init__(self, description: str = "Çoklu işlem"):
        self.commands: List[Command] = []
        self.description = description
    
    def add_command(self, command: Command):
        """Komut ekle"""
        self.commands.append(command)
    
    def execute(self) -> bool:
        executed = []
        for cmd in self.commands:
            if cmd.execute():
                executed.append(cmd)
            else:
                # Bir komut başarısız olursa hepsini geri al
                for exc_cmd in reversed(executed):
                    exc_cmd.undo()
                return False
        return True
    
    def undo(self) -> bool:
        # Ters sırada geri al
        for cmd in reversed(self.commands):
            if not cmd.undo():
                return False
        return True
    
    def get_description(self) -> str:
        return self.description

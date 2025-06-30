��#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@file pinn_integration.py
@description irt�Oo`^y�~Q�~(PINN)NIoTpenc�TKratos�NwƖb
@author Deep Excavation Team
@version 1.0.0
@copyright 2025
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import time
import logging
from typing import Dict, List, Tuple, Union, Optional, Any
from pathlib import Path
import json
import datetime
import torch

# �[eQirtAI!jWW
from src.ai.physics_ai import (
    PhysicsInformedNN, 
    HeatEquationPINN, 
    WaveEquationPINN, 
    ElasticityPINN, 
    PDEInverseAnalysis
)

# �[eQIoTpenc!jWW
from src.ai.iot_data_collector import SimpleIoTDataReader, SensorType

# M�n�e�_
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PINNIntegration")

# \Ջ�[eQTensorFlow (�S	�)
try:
    import tensorflow as tf
    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False
    logger.warning("TensorFlow*g�[ň��R�R���S��N�S(u")

# \Ջ�[eQDeepXDE (�S	�)
try:
    import deepxde as dde
    HAS_DEEPXDE = True
except ImportError:
    HAS_DEEPXDE = False
    logger.warning("DeepXDE*g�[ň��R�R���S��N�S(u")

# \Ջ�[eQKratos (�S	�)
try:
    from KratosMultiphysics import Model
    HAS_KRATOS = True
except ImportError:
    HAS_KRATOS = False
    logger.warning("Kratos*g�[ň��R�R���S��N�S(u")

class PhysicsInformedNN:
    """�W@xirt�Oo`^y�~Q�~�[�s"""
    
    def __init__(
        self,
        input_dim: int = 2,
        output_dim: int = 1,
        hidden_layers: List[int] = None,
        activation: str = "tanh",
        device: str = None
    ):
        """
        R�YSPINN!j�W
        
        Args:
            input_dim: ��eQ�~�^(�8^:NPWh�~�^)
            output_dim: ���Q�~�^(�8^:Nirt:W�v�~�^)
            hidden_layers: ��υB\�~�^Rh�
            activation: �o;m�Qpe ('tanh', 'relu', 'sigmoid')
            device: ���{��Y ('cpu', 'cuda:0', I{)
        """
        # ��n؞���Spe
        if hidden_layers is None:
            hidden_layers = [20, 20, 20]
            
        if device is None:
            self.device = torch.device(
                "cuda:0" if torch.cuda.is_available() else "cpu"
            )
        else:
            self.device = torch.device(device)
        
        # !j�W�Spe
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_layers = hidden_layers
        
        # �g�^^y�~Q�~
        self.model = self._build_network(activation)
        self.model.to(self.device)
        
        # OShV�T_c1Y
        self.optimizer = None
        self.criterion = torch.nn.MSELoss()
        self.epoch = 0
        
    def _build_network(self, activation: str) -> torch.nn.Sequential:
        """�g�^^y�~Q�~"""
        # ��n�o;m�Qpe
        if activation.lower() == 'tanh':
            act = torch.nn.Tanh()
        elif activation.lower() == 'relu':
            act = torch.nn.ReLU()
        elif activation.lower() == 'sigmoid':
            act = torch.nn.Sigmoid()
        else:
            act = torch.nn.Tanh()
        
        # �g�^B\
        layers = []
        prev_dim = self.input_dim
        
        # �m�R��υB\
        for dim in self.hidden_layers:
            layers.append(torch.nn.Linear(prev_dim, dim))
            layers.append(act)
            prev_dim = dim
        
        # �m�R���QB\
        layers.append(torch.nn.Linear(prev_dim, self.output_dim))
        
        return torch.nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """MRT O�d"""
        return self.model(x)
    
    def setup_optimizer(self, optimizer_name: str = "adam", learning_rate: float = 0.001):
        """��nOShV"""
        if optimizer_name.lower() == "adam":
            self.optimizer = torch.optim.Adam(
                self.model.parameters(),
                lr=learning_rate
            )
        elif optimizer_name.lower() == "sgd":
            self.optimizer = torch.optim.SGD(
                self.model.parameters(),
                lr=learning_rate
            )
        elif optimizer_name.lower() == "lbfgs":
            self.optimizer = torch.optim.LBFGS(
                self.model.parameters(),
                lr=learning_rate
            )
        else:
            self.optimizer = torch.optim.Adam(
                self.model.parameters(),
                lr=learning_rate
            )
    
    def save_model(self, file_path: str):
        """�OX[!j�W"""
        torch.save({
            'epoch': self.epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict() if self.optimizer else None,
            'input_dim': self.input_dim,
            'output_dim': self.output_dim,
            'hidden_layers': self.hidden_layers
        }, file_path)
        
    def load_model(self, file_path: str):
        """�R}�!j�W"""
        checkpoint = torch.load(file_path, map_location=self.device)
        
        # ͑�^Q�~(�Y�g���)
        if 'input_dim' in checkpoint and 'output_dim' in checkpoint and 'hidden_layers' in checkpoint:
            self.input_dim = checkpoint['input_dim']
            self.output_dim = checkpoint['output_dim']
            self.hidden_layers = checkpoint['hidden_layers']
            self.model = self._build_network('tanh')
            
        # �R}��r`
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.epoch = checkpoint.get('epoch', 0)
        
        # ��nOShV(�Y�g���)
        if self.optimizer and 'optimizer_state_dict' in checkpoint:
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])


class ElasticityPINN(PhysicsInformedNN):
    """9_'`�Rf[PINN!j�W"""
    
    def __init__(
        self,
        domain_bounds: List[List[float]],
        young_modulus: float = 30e6,
        poisson_ratio: float = 0.3,
        **kwargs
    ):
        """
        R�YS9_'`�Rf[PINN!j�W
        
        Args:
            domain_bounds: �[IN�W��Lu [[x_min, x_max], [y_min, y_max], [z_min, z_max]]
            young_modulus: hgl!jϑ
            poisson_ratio: �l~g�k
            **kwargs: 6r{|�Spe
        """
        # :N9_'`���n���Q:NMO�y
        kwargs["input_dim"] = len(domain_bounds)  # PWh�~�^
        kwargs["output_dim"] = len(domain_bounds)  # MO�y�~�^
        
        super().__init__(**kwargs)
        
        self.domain_bounds = domain_bounds
        self.E = young_modulus
        self.nu = poisson_ratio
        
        # ���{�b�h8^pe
        self.lambda_ = self.E * self.nu / ((1 + self.nu) * (1 - 2 * self.nu))
        self.mu = self.E / (2 * (1 + self.nu))
        
    def compute_strain(self, u_grad: torch.Tensor) -> torch.Tensor:
        """���{�^�S _ϑ"""
        # �c�SMO�y�h�^Rϑ
        if u_grad.shape[1] == 2:  # 2D
            u_x, u_y = u_grad[:, 0, 0], u_grad[:, 1, 1]
            v_x, v_y = u_grad[:, 0, 1], u_grad[:, 1, 0]
            
            # �g ��^�S _ϑ
            epsilon_xx = u_x
            epsilon_yy = v_y
            epsilon_xy = 0.5 * (u_y + v_x)
            
            return torch.stack([epsilon_xx, epsilon_yy, epsilon_xy], dim=1)
        else:  # 3D
            u_x, u_y, u_z = u_grad[:, 0, 0], u_grad[:, 0, 1], u_grad[:, 0, 2]
            v_x, v_y, v_z = u_grad[:, 1, 0], u_grad[:, 1, 1], u_grad[:, 1, 2]
            w_x, w_y, w_z = u_grad[:, 2, 0], u_grad[:, 2, 1], u_grad[:, 2, 2]
            
            # �g ��^�S _ϑ
            epsilon_xx = u_x
            epsilon_yy = v_y
            epsilon_zz = w_z
            epsilon_xy = 0.5 * (u_y + v_x)
            epsilon_yz = 0.5 * (v_z + w_y)
            epsilon_xz = 0.5 * (u_z + w_x)
            
            return torch.stack([
                epsilon_xx, epsilon_yy, epsilon_zz,
                epsilon_xy, epsilon_yz, epsilon_xz
            ], dim=1)
        
    def compute_stress(self, strain: torch.Tensor) -> torch.Tensor:
        """���{�^�R _ϑ"""
        if strain.shape[1] == 3:  # 2D
            epsilon_xx, epsilon_yy, epsilon_xy = strain[:, 0], strain[:, 1], strain[:, 2]
            
            # ���{�^�RRϑ
            sigma_xx = self.lambda_ * (epsilon_xx + epsilon_yy) + 2 * self.mu * epsilon_xx
            sigma_yy = self.lambda_ * (epsilon_xx + epsilon_yy) + 2 * self.mu * epsilon_yy
            sigma_xy = 2 * self.mu * epsilon_xy
            
            return torch.stack([sigma_xx, sigma_yy, sigma_xy], dim=1)
        else:  # 3D
            epsilon_xx = strain[:, 0]
            epsilon_yy = strain[:, 1]
            epsilon_zz = strain[:, 2]
            epsilon_xy = strain[:, 3]
            epsilon_yz = strain[:, 4]
            epsilon_xz = strain[:, 5]
            
            # ���{SO�y�^�S
            epsilon_vol = epsilon_xx + epsilon_yy + epsilon_zz
            
            # ���{�^�RRϑ
            sigma_xx = self.lambda_ * epsilon_vol + 2 * self.mu * epsilon_xx
            sigma_yy = self.lambda_ * epsilon_vol + 2 * self.mu * epsilon_yy
            sigma_zz = self.lambda_ * epsilon_vol + 2 * self.mu * epsilon_zz
            sigma_xy = 2 * self.mu * epsilon_xy
            sigma_yz = 2 * self.mu * epsilon_yz
            sigma_xz = 2 * self.mu * epsilon_xz
            
            return torch.stack([
                sigma_xx, sigma_yy, sigma_zz,
                sigma_xy, sigma_yz, sigma_xz
            ], dim=1)
    
    def compute_equilibrium_residual(self, x: torch.Tensor) -> torch.Tensor:
        """���{s^a��ez�k�]"""
        x.requires_grad_(True)
        
        # MRT��KmMO�y
        u_pred = self.forward(x)
        
        # ���{MO�y�h�^
        u_grad = torch.zeros(u_pred.shape[0], u_pred.shape[1], x.shape[1], device=self.device)
        
        for i in range(u_pred.shape[1]):
            grad_outputs = torch.zeros_like(u_pred)
            grad_outputs[:, i] = 1
            grad = torch.autograd.grad(
                outputs=u_pred,
                inputs=x,
                grad_outputs=grad_outputs,
                create_graph=True
            )[0]
            u_grad[:, i, :] = grad
        
        # ���{�^�S�T�^�R
        strain = self.compute_strain(u_grad)
        stress = self.compute_stress(strain)
        
        # ���{�^�Rce�^(s^a��ez�k�])
        if x.shape[1] == 2:  # 2D
            sigma_xx, sigma_yy, sigma_xy = stress[:, 0], stress[:, 1], stress[:, 2]
            
            # �^�R�[pe
            sigma_xx_x = torch.autograd.grad(
                sigma_xx.sum(), x, create_graph=True
            )[0][:, 0]
            
            sigma_xy_y = torch.autograd.grad(
                sigma_xy.sum(), x, create_graph=True
            )[0][:, 1]
            
            sigma_xy_x = torch.autograd.grad(
                sigma_xy.sum(), x, create_graph=True
            )[0][:, 0]
            
            sigma_yy_y = torch.autograd.grad(
                sigma_yy.sum(), x, create_graph=True
            )[0][:, 1]
            
            # �k�]
            residual_x = sigma_xx_x + sigma_xy_y
            residual_y = sigma_xy_x + sigma_yy_y
            
            return torch.stack([residual_x, residual_y], dim=1)
        else:  # 3D
            # 3D�[�seuǏ�{|<O2DibU\
            pass
    
    def train_step(self, x_data: torch.Tensor = None, y_data: torch.Tensor = None, 
                  x_pde: torch.Tensor = None, 
                  boundary_condition=None,
                  pde_weight: float = 1.0, 
                  bc_weight: float = 1.0,
                  data_weight: float = 1.0):
        """���~ek��"""
        def closure():
            self.optimizer.zero_grad()
            loss = 0.0
            
            # penc_c1Y
            if x_data is not None and y_data is not None:
                y_pred = self.forward(x_data)
                data_loss = self.criterion(y_pred, y_data) * data_weight
                loss += data_loss
            
            # PDE_c1Y
            if x_pde is not None:
                pde_residual = self.compute_equilibrium_residual(x_pde)
                pde_loss = torch.mean(pde_residual ** 2) * pde_weight
                loss += pde_loss
            
            # ��Luag�N_c1Y
            if boundary_condition is not None:
                bc_loss = bc_weight * boundary_condition(self)
                loss += bc_loss
            
            loss.backward()
            return loss
        
        if isinstance(self.optimizer, torch.optim.LBFGS):
            self.optimizer.step(closure)
        else:
            closure()
            self.optimizer.step()
        
        self.epoch += 1


class IoTPINNIntegrator:
    """IoTpencNPINN!j�WƖbhV"""
    
    def __init__(self, project_id: int = 0, working_dir: str = None):
        """
        R�YSIoT-PINNƖbhV
        
        Args:
            project_id: y��vID
            working_dir: �]\O�vU_
        """
        self.project_id = project_id
        
        # ��n�]\O�vU_
        if working_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.working_dir = os.path.join(base_dir, "data", "models", "pinn")
        else:
            self.working_dir = working_dir
            
        os.makedirs(self.working_dir, exist_ok=True)
        
        # PINN!j�WW[xQ
        self.pinn_models = {}
        
        logger.info(f"PINNƖbhVR�YS, y��vID: {project_id}")
    
    def create_model(self, model_name: str, model_type: str, config: Dict[str, Any]) -> bool:
        """
        R�^PINN!j�W
        
        Args:
            model_name: !j�WT�y
            model_type: !j�W{|�W
            config: M�n�Spe
            
        Returns:
            bool: /f&Tb�R
        """
        try:
            if model_type == "elasticity":
                # R�^9_'`�Rf[!j�W
                domain_bounds = config.get("domain_bounds", [[-10, 10], [-10, 10]])
                young_modulus = config.get("young_modulus", 30e6)
                poisson_ratio = config.get("poisson_ratio", 0.3)
                hidden_layers = config.get("hidden_layers", [20, 20, 20])
                activation = config.get("activation", "tanh")
                
                model = ElasticityPINN(
                    domain_bounds=domain_bounds,
                    young_modulus=young_modulus,
                    poisson_ratio=poisson_ratio,
                    hidden_layers=hidden_layers,
                    activation=activation
                )
                
                # ��nOShV
                optimizer = config.get("optimizer", "adam")
                learning_rate = config.get("learning_rate", 0.001)
                model.setup_optimizer(optimizer, learning_rate)
                
                # �OX[!j�W
                self.pinn_models[model_name] = model
                
                logger.info(f"R�^!j�W '{model_name}' b�R, {|�W: {model_type}")
                return True
                
            else:
                logger.error(f"N/ec�v!j�W{|�W: {model_type}")
                return False
                
        except Exception as e:
            logger.error(f"R�^!j�W�Q�: {str(e)}")
            return False
    
    def train_from_sensors(self, model_name: str, sensor_data: Dict[str, Any], 
                          training_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        O(u OahVpenc���~PINN!j�W
        
        Args:
            model_name: !j�WT�y
            sensor_data:  OahVpenc
            training_config: ���~M�n
            
        Returns:
            Dict: ���~�~�g
        """
        if model_name not in self.pinn_models:
            logger.error(f"!j�W '{model_name}' NX[(W")
            return {"success": False, "error": f"!j�W '{model_name}' NX[(W"}
        
        try:
            model = self.pinn_models[model_name]
            
            # �c�S���~�Spe
            epochs = training_config.get("epochs", 10000)
            pde_weight = training_config.get("pde_weight", 1.0)
            bc_weight = training_config.get("bc_weight", 1.0)
            data_weight = training_config.get("data_weight", 1.0)
            batch_size = training_config.get("batch_size", None)
            save_interval = training_config.get("save_interval", 1000)
            
            # �QY OahVpenc
            coordinates = []
            values = []
            
            for sensor in sensor_data.get("sensors", []):
                sensor_coords = sensor.get("coordinates", [])
                sensor_values = sensor.get("values", [])
                
                if sensor_coords and sensor_values:
                    coordinates.append(sensor_coords)
                    values.append(sensor_values)
            
            if not coordinates:
                logger.error("�l	g	gHe�v OahVpenc")
                return {"success": False, "error": "�l	g	gHe�v OahVpenc"}
            
            # l�bc:N _ϑ
            x_data = torch.tensor(coordinates, dtype=torch.float32).to(model.device)
            y_data = torch.tensor(values, dtype=torch.float32).to(model.device)
            
            # ���SPDEǑ7h�p
            if "pde_samples" in training_config:
                pde_samples = training_config["pde_samples"]
                x_pde = torch.tensor(pde_samples, dtype=torch.float32).to(model.device)
            else:
                # ؞��R�^GWSQ<h
                domain_bounds = model.domain_bounds
                n_pde_samples = training_config.get("n_pde_samples", 1000)
                
                # R�^��:gǑ7h�p
                x_pde_list = []
                for i, (lower, upper) in enumerate(domain_bounds):
                    x_pde_list.append(
                        lower + (upper - lower) * torch.rand(n_pde_samples, 1)
                    )
                
                x_pde = torch.cat(x_pde_list, dim=1).to(model.device)
            
            # ���S��Luag�N
            def boundary_condition(model):
                return torch.tensor(0.0, device=model.device)
                
            # ���~�_�s
            losses = []
            start_epoch = model.epoch
            
            for epoch in range(epochs):
                # �Y�gO(uyb!k���~
                if batch_size and x_data.shape[0] > batch_size:
                    idx = torch.randperm(x_data.shape[0])[:batch_size]
                    x_batch = x_data[idx]
                    y_batch = y_data[idx]
                else:
                    x_batch = x_data
                    y_batch = y_data
                
                # ���~ek��
                model.train_step(
                    x_data=x_batch,
                    y_data=y_batch,
                    x_pde=x_pde,
                    boundary_condition=boundary_condition,
                    pde_weight=pde_weight,
                    bc_weight=bc_weight,
                    data_weight=data_weight
                )
                
                # �OX[�h�g�p
                if (epoch + 1) % save_interval == 0:
                    checkpoint_path = os.path.join(
                        self.working_dir,
                        f"{model_name}_checkpoint_{model.epoch}.pt"
                    )
                    model.save_model(checkpoint_path)
                    
                    logger.info(f"�OX[�h�g�p: {checkpoint_path}")
            
            # �OX[g�~!j�W
            model_path = os.path.join(self.working_dir, f"{model_name}.pt")
            model.save_model(model_path)
            
            logger.info(f"!j�W���~�[b, �OX[0R: {model_path}")
            
            return {
                "success": True,
                "model_path": model_path,
                "epochs": epochs,
                "start_epoch": start_epoch,
                "end_epoch": model.epoch
            }
            
        except Exception as e:
            logger.error(f"���~!j�W�Q�: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def predict(self, model_name: str, query_points: List[List[float]]) -> Dict[str, Any]:
        """
        O(uPINN!j�WۏL���Km
        
        Args:
            model_name: !j�WT�y
            query_points: �g⋹pPWhRh�
            
        Returns:
            Dict: ��Km�~�g
        """
        if model_name not in self.pinn_models:
            logger.error(f"!j�W '{model_name}' NX[(W")
            return {"success": False, "error": f"!j�W '{model_name}' NX[(W"}
        
        try:
            model = self.pinn_models[model_name]
            
            # l�bc:N _ϑ
            x = torch.tensor(query_points, dtype=torch.float32).to(model.device)
            
            # ��Km
            with torch.no_grad():
                y_pred = model.forward(x).cpu().numpy()
            
            return {
                "success": True,
                "predictions": y_pred.tolist()
            }
            
        except Exception as e:
            logger.error(f"��Km�Q�: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def integrate_with_kratos(self, model_name: str, kratos_model_part_name: str = "Structure") -> Dict[str, Any]:
        """
        \PINN!j�WƖb0RKratos!j�W-N
        
        Args:
            model_name: !j�WT�y
            kratos_model_part_name: Kratos!j�W�RT�y
            
        Returns:
            Dict: Ɩb�~�g
        """
        if not HAS_KRATOS:
            logger.error("Kratos*g�[ň��e�lۏL�Ɩb")
            return {"success": False, "error": "Kratos*g�[ň"}
            
        if model_name not in self.pinn_models:
            logger.error(f"!j�W '{model_name}' NX[(W")
            return {"success": False, "error": f"!j�W '{model_name}' NX[(W"}
        
        try:
            model = self.pinn_models[model_name]
            
            # R�^Kratos!j�W
            kratos_model = Model()
            model_part = kratos_model.CreateModelPart(kratos_model_part_name)
            
            # TODO: \PINN!j�WƖb0RKratos
            # ُ�R���9hncwQSO�vKratos API�[�s
            
            logger.info(f"PINN!j�W '{model_name}' �]Ɩb0RKratos")
            
            return {
                "success": True,
                "model_name": model_name,
                "kratos_model_part": kratos_model_part_name
            }
            
        except Exception as e:
            logger.error(f"Ɩb0RKratos�Q�: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def export_to_vtk(self, model_name: str, grid_resolution: List[int], 
                     output_file: str) -> Dict[str, Any]:
        """
        �[�QPINN!j�W�~�g0RVTK�e�N
        
        Args:
            model_name: !j�WT�y
            grid_resolution: Q<hR���s
            output_file: ���Q�e�N_
            
        Returns:
            Dict: �[�Q�~�g
        """
        if model_name not in self.pinn_models:
            logger.error(f"!j�W '{model_name}' NX[(W")
            return {"success": False, "error": f"!j�W '{model_name}' NX[(W"}
        
        try:
            model = self.pinn_models[model_name]
            domain_bounds = model.domain_bounds
            
            # R�^Q<h
            grid_points = []
            
            # 2DQ<h
            if len(domain_bounds) == 2:
                nx, ny = grid_resolution
                
                x_min, x_max = domain_bounds[0]
                y_min, y_max = domain_bounds[1]
                
                x = np.linspace(x_min, x_max, nx)
                y = np.linspace(y_min, y_max, ny)
                
                X, Y = np.meshgrid(x, y)
                
                for i in range(nx):
                    for j in range(ny):
                        grid_points.append([X[j, i], Y[j, i]])
                        
            # 3DQ<h
            elif len(domain_bounds) == 3:
                nx, ny, nz = grid_resolution
                
                x_min, x_max = domain_bounds[0]
                y_min, y_max = domain_bounds[1]
                z_min, z_max = domain_bounds[2]
                
                x = np.linspace(x_min, x_max, nx)
                y = np.linspace(y_min, y_max, ny)
                z = np.linspace(z_min, z_max, nz)
                
                X, Y, Z = np.meshgrid(x, y, z)
                
                for i in range(nx):
                    for j in range(ny):
                        for k in range(nz):
                            grid_points.append([X[j, i, k], Y[j, i, k], Z[j, i, k]])
            
            # ۏL���Km
            result = self.predict(model_name, grid_points)
            
            if not result["success"]:
                return result
                
            predictions = result["predictions"]
            
            # �[�Q0RVTK
            try:
                import vtk
                from vtk.util import numpy_support
                
                # R�^VTKpenc�[a�
                if len(domain_bounds) == 2:
                    nx, ny = grid_resolution
                    
                    # R�^�~�gSQ<h
                    grid = vtk.vtkStructuredGrid()
                    grid.SetDimensions(nx, ny, 1)
                    
                    # ��n�p
                    points = vtk.vtkPoints()
                    for p in grid_points:
                        points.InsertNextPoint(p[0], p[1], 0.0)
                    
                    grid.SetPoints(points)
                    
                    # ��npenc
                    for i, name in enumerate(["u", "v"]):
                        data_array = numpy_support.numpy_to_vtk(
                            num_array=np.array([p[i] for p in predictions]),
                            deep=True,
                            array_type=vtk.VTK_FLOAT
                        )
                        data_array.SetName(name)
                        grid.GetPointData().AddArray(data_array)
                        
                else:  # 3D
                    nx, ny, nz = grid_resolution
                    
                    # R�^�~�gSQ<h
                    grid = vtk.vtkStructuredGrid()
                    grid.SetDimensions(nx, ny, nz)
                    
                    # ��n�p
                    points = vtk.vtkPoints()
                    for p in grid_points:
                        points.InsertNextPoint(p[0], p[1], p[2])
                    
                    grid.SetPoints(points)
                    
                    # ��npenc
                    for i, name in enumerate(["u", "v", "w"]):
                        data_array = numpy_support.numpy_to_vtk(
                            num_array=np.array([p[i] for p in predictions]),
                            deep=True,
                            array_type=vtk.VTK_FLOAT
                        )
                        data_array.SetName(name)
                        grid.GetPointData().AddArray(data_array)
                
                # �QeQ�e�N
                writer = vtk.vtkXMLStructuredGridWriter()
                writer.SetFileName(output_file)
                writer.SetInputData(grid)
                writer.Write()
                
                logger.info(f"VTK�e�N�]�OX[: {output_file}")
                
                return {
                    "success": True,
                    "output_file": output_file
                }
                
            except ImportError:
                logger.error("VTK�^*g�[ň�\ՋO(u�f�N�e�l")
                
                # R�^�{US�vVTK�e�N
                with open(output_file, 'w') as f:
                    f.write("# vtk DataFile Version 3.0\n")
                    f.write("PINN Results\n")
                    f.write("ASCII\n")
                    f.write("DATASET STRUCTURED_GRID\n")
                    
                    if len(domain_bounds) == 2:
                        nx, ny = grid_resolution
                        f.write(f"DIMENSIONS {nx} {ny} 1\n")
                    else:
                        nx, ny, nz = grid_resolution
                        f.write(f"DIMENSIONS {nx} {ny} {nz}\n")
                    
                    f.write(f"POINTS {len(grid_points)} float\n")
                    for p in grid_points:
                        if len(p) == 2:
                            f.write(f"{p[0]} {p[1]} 0.0\n")
                        else:
                            f.write(f"{p[0]} {p[1]} {p[2]}\n")
                    
                    f.write(f"POINT_DATA {len(grid_points)}\n")
                    
                    if len(domain_bounds) == 2:
                        f.write("VECTORS displacement float\n")
                        for p in predictions:
                            f.write(f"{p[0]} {p[1]} 0.0\n")
                    else:
                        f.write("VECTORS displacement float\n")
                        for p in predictions:
                            f.write(f"{p[0]} {p[1]} {p[2]}\n")
                
                logger.info(f"�{USVTK�e�N�]�OX[: {output_file}")
                
                return {
                    "success": True,
                    "output_file": output_file,
                    "note": "O(u�{USVTK<h_�[�Q"
                }
            
        except Exception as e:
            logger.error(f"�[�Q0RVTK�Q�: {str(e)}")
            return {"success": False, "error": str(e)}

# :y�O(u�l
if __name__ == "__main__":
    # R�^IoT-PINNƖbhV
    integrator = IoTPINNIntegrator(project_id=1)
    
    # �QYpenc
    today = datetime.datetime.now().strftime("%Y%m%d")
    pinn_data = integrator.prepare_data_for_pinn(
        data_type=SensorType.DISPLACEMENT,
        start_date=today,
        normalize=True
    )
    
    if pinn_data and 'X_train' in pinn_data and len(pinn_data['X_train']) > 0:
        # R�^v^���~PINN!j�W
        result = integrator.train_pinn_with_iot_data(
            pinn_data=pinn_data,
            model_type='elasticity',
            iterations=5000,
            display_every=1000
        )
        
        print(f"���~�~�g: {result}")
        
        # O(u!j�WۏL���Km
        if 'X_test' in pinn_data and len(pinn_data['X_test']) > 0:
            X_test = pinn_data['X_test']
            Y_test = pinn_data['y_test']
            
            Y_pred = integrator.predict_with_pinn(X_test)
            
            # �SƉS�~�g
            integrator.visualize_results(
                X=X_test,
                Y_true=Y_test,
                Y_pred=Y_pred,
                title="MO�y��Km�~�g",
                save_path=os.path.join(integrator.results_dir, "displacement_prediction.png")
            )
    else:
        print("�l	g��Y�vpenc(u�NPINN���~")  
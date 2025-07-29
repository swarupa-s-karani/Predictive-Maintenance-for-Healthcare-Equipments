// frontend/src/pages/AdminEquipments.jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import MaintenanceLogs from './MaintenanceLogs';
import Calendar from "react-calendar";
import "react-calendar/dist/Calendar.css";
import axios from "axios";

export default function AdminEquipments() {
  const [equipments, setEquipments] = useState([]);
  const [users, setUsers] = useState([]);
  const [tab, setTab] = useState('equipment');
  const [edaImageBase64, setEdaImageBase64] = useState('');
  const [profile, setProfile] = useState({});
  const [equipmentForm, setEquipmentForm] = useState({ equipment_id: '', type: '', manufacturer: '', location: '', criticality: '', installation_date: '' });
  const [userForm, setUserForm] = useState({ personnel_id: '', name: '', role: '', department: '', experience_years: '', username: '', password: '' });
  const [filters, setFilters] = useState({ type: '', location: '', health: '' });
  const [healthMap, setHealthMap] = useState({});
  const [scheduledMap, setScheduledMap] = useState({});
  const [showAddEquipment, setShowAddEquipment] = useState(false);
  const [showAddUser, setShowAddUser] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ show: false, type: '', id: '' });
  const [scheduleForm, setScheduleForm] = useState({ show: false, id: '', maintenance_type: '', technician_id: '', date: '', issue_description: '' });
  const [pendingReviews, setPendingReviews] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [issueDescription, setIssueDescription] = useState('');
  const [showCalendar, setShowCalendar] = useState(false);
  const [selectedEquipmentId, setSelectedEquipmentId] = useState(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewData, setReviewData] = useState({});
  const [serviceRating, setServiceRating] = useState('');
  const [completionStatus, setCompletionStatus] = useState('');
  const [alert, setAlert] = useState({ show: false, message: '', type: '' });

  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  // Move showAlert function to component level so it's accessible everywhere
  const showAlert = (message, type = 'info') => {
    setAlert({ show: true, message, type });
    setTimeout(() => {
      setAlert({ show: false, message: '', type: '' });
    }, 4000); // Auto-hide after 4 seconds
  };

  useEffect(() => {
    fetchData();
    fetchPendingReviews();
  }, []);

  
  const fetchData = async () => {
    try {
      // Fetch equipments
      const resEquip = await api.get('/equipments', { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      setEquipments(resEquip.data.equipments || []);

      // Fetch users
      const resUsers = await api.get('/users', { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      setUsers(resUsers.data.users || []);

      // Fetch profile
      const resProfile = await api.get('/users/me', { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      setProfile(resProfile.data || {});

      // Fetch EDA image
      const resEDA = await api.get('/eda/overall-eda-image', { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      setEdaImageBase64(resEDA.data.image_base64 || '');

      // Run predictions - but don't let this affect other data
      try {
        await api.post('/predict', {}, { 
          headers: { Authorization: `Bearer ${token}` } 
        });
      } catch (predErr) {
        console.warn("Prediction failed:", predErr);
      }
      
      // Fetch priority data for each equipment - with error handling
      const equipmentsList = resEquip.data.equipments || [];
      await Promise.allSettled(equipmentsList.map(async ([id]) => {
        try {
          await api.get(`/maintenance-log/priority/${id}`, { 
            headers: { Authorization: `Bearer ${token}` } 
          });
        } catch (err) {
          console.warn(`Failed to fetch priority for equipment ${id}:`, err);
        }
      }));

      // Fetch health badges and scheduled map
      await fetchHealthBadges(equipmentsList);
      await fetchScheduledMap(equipmentsList);
      await fetchPendingReviews();
      
    } catch (error) {
      console.error("Error in fetchData:", error);
    }
  };

  const fetchHealthBadges = async (equipmentsList) => {
    const map = {};
    
    await Promise.allSettled(equipmentsList.map(async ([id]) => {
      try {
        const res = await api.get(`/maintenance-log/priority/${id}`, { 
          headers: { Authorization: `Bearer ${token}` } 
        });
        
        const { predicted_to_fail, maintenance_needs } = res.data;
        console.log(`Health data for ${id}:`, { predicted_to_fail, maintenance_needs });
        
        const isRisk = predicted_to_fail || Object.values(maintenance_needs || {}).includes('High');
        
        map[id] = isRisk ? {
          label: 'High Risk',
          msg: `${predicted_to_fail ? 'Predicted to Fail' : ''}${predicted_to_fail && maintenance_needs ? ', ' : ''}${Object.entries(maintenance_needs || {}).filter(([_, v]) => v === 'High').map(([k]) => k.charAt(0).toUpperCase() + k.slice(1)).join(', ')} maintenance`
        } : { 
          label: 'Healthy', 
          msg: '' 
        };
        
      } catch (err) {
        console.error(`Error fetching health for ${id}:`, err);
        map[id] = { label: 'Unknown', msg: 'Error loading health status' };
      }
    }));
    
    console.log('Complete health map:', map);
    setHealthMap(map);
  };

  const fetchScheduledMap = async (equipmentsList) => {
    const map = {};
    await Promise.all(equipmentsList.map(async ([id]) => {
      try {
        const res = await api.get(`/maintenance-log/by-equipment/${id}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        // Make sure to check for 'Scheduled' status properly
        map[id] = res.data.logs?.some(log => log.status === 'Scheduled') || false;
      } catch {
        map[id] = false;
      }
    }));
    setScheduledMap(map);
  };

  const fetchPendingReviews = async () => {
    try {
      // Using your backend route: GET /maintenance-log/pending-reviews
      const res = await api.get("/maintenance-log/pending-reviews", {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Your backend returns {reviews: [...]} format
      setPendingReviews(res.data.reviews || []);
    } catch (err) {
      console.error("Error fetching pending reviews", err);
    }
  };

  const handleAddEquipment = async () => {
    await api.post('/equipments', equipmentForm, { headers: { Authorization: `Bearer ${token}` } });
    setShowAddEquipment(false);
    fetchData();
  };

  const handleAddUser = async () => {
    await api.post('/users', userForm, { headers: { Authorization: `Bearer ${token}` } });
    setShowAddUser(false);
    fetchData();
  };

  const handleDelete = async () => {
    const { type, id } = confirmDialog;
    const url = type === 'equipment' ? `/equipments/${id}` : `/users/${id}`;
    await api.delete(url, { headers: { Authorization: `Bearer ${token}` } });
    setConfirmDialog({ show: false, type: '', id: '' });
    fetchData();
  };

  const logout = () => {
    localStorage.removeItem('token');
    navigate('/');
  };

  const handleSchedule = async () => {
    if (!issueDescription) {
      showAlert("Please fill all fields before submitting.");
      return;
    }

    try {
      const res = await api.put(
          `/maintenance-log/schedule/${scheduleForm.id}`,
        {
          maintenance_type: "Preventive",
          // technician_id: null, // null if not auto-assigned
          date: selectedDate.toISOString().split("T")[0],
          issue_description: issueDescription,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      showAlert(res.data.message || "Maintenance scheduled successfully.");
      setScheduleForm({ show: false, id: '', maintenance_type: '', technician_id: '', date: '', issue_description: '' });
      setIssueDescription("");

      // Re-fetch all updated data after scheduling
      await fetchData();

    } catch (err) {
      showAlert(err?.response?.data?.detail || "Error scheduling maintenance");
      console.error(err);
    }
  };


  const getBadge = (id) => {
    const info = healthMap[id];
    if (!info) return <span className="text-xs px-2 py-1 rounded bg-gray-400 text-white">Loading...</span>;

    return (
      <div>
        <span className={`text-xs px-2 py-1 rounded ${info.label === 'High Risk' ? 'bg-red-600' : 'bg-green-600'} text-white`}>
          {info.label}
        </span>
        {info.msg && <p className="text-xs mt-1 text-red-600">{info.msg}</p>}
      </div>
    );
  };

  
  // Update the handleReviewMaintenance function in AdminEquipments.jsx

  const handleReviewMaintenance = async (maintenanceId) => {
    if (!serviceRating || !completionStatus) {
      showAlert("Please fill all required fields.", 'warning');
      return;
    }

    try {
      console.log('Submitting review:', {
        maintenance_id: maintenanceId,
        service_rating: parseInt(serviceRating),
        completion_status: completionStatus
      });

      const res = await api.put(`/maintenance-log/review-completion/${maintenanceId}`, {
        service_rating: parseInt(serviceRating),
        completion_status: completionStatus
        // Remove the "status" field - let backend handle it
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      console.log('Review response:', res.data);

      // Success message based on approval status
      const statusMessage = completionStatus === 'Approved' 
        ? "Maintenance approved and marked as completed. Equipment health status updated."
        : "Maintenance requires additional work. Returned to technician queue.";

      showAlert(statusMessage, completionStatus === 'Approved' ? 'success' : 'warning');
      
      // Reset modal
      setShowReviewModal(false);
      setServiceRating('');
      setCompletionStatus('');
      const equipmentId = reviewData.equipment_id;
      setReviewData({});
      
      // CRITICAL: If approved, force refresh health status immediately
      if (completionStatus === 'Approved' && equipmentId) {
        console.log(`Forcing health refresh for equipment: ${equipmentId}`);
        
        // Wait a moment for backend to process
        await new Promise(resolve => setTimeout(resolve, 500));
        
        try {
          // Force priority recalculation for this specific equipment
          const priorityRes = await api.get(`/maintenance-log/priority/${equipmentId}`, { 
            headers: { Authorization: `Bearer ${token}` } 
          });
          
          console.log('Updated priority data:', priorityRes.data);
          
          // Update health badges immediately
          const updatedHealthMap = { ...healthMap };
          const { predicted_to_fail, maintenance_needs } = priorityRes.data;
          const isRisk = predicted_to_fail || Object.values(maintenance_needs || {}).includes('High');
          
          updatedHealthMap[equipmentId] = isRisk ? {
            label: 'High Risk',
            msg: `${predicted_to_fail ? 'Predicted to Fail' : ''}${predicted_to_fail && maintenance_needs ? ', ' : ''}${Object.entries(maintenance_needs || {}).filter(([_, v]) => v === 'High').map(([k]) => k.charAt(0).toUpperCase() + k.slice(1)).join(', ')} maintenance`
          } : { 
            label: 'Healthy', 
            msg: '' 
          };
          
          setHealthMap(updatedHealthMap);
          console.log(`Updated health for ${equipmentId}:`, updatedHealthMap[equipmentId]);
          
          // Also update scheduled map
          const scheduledRes = await api.get(`/maintenance-log/by-equipment/${equipmentId}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
          
          const updatedScheduledMap = { ...scheduledMap };
          updatedScheduledMap[equipmentId] = scheduledRes.data.logs?.some(log => log.status === 'Scheduled') || false;
          setScheduledMap(updatedScheduledMap);
          
        } catch (healthErr) {
          console.error("Failed to update health status:", healthErr);
          showAlert("Maintenance completed but failed to refresh health status. Please refresh the page.", 'warning');
        }
      }
      
      // Refresh all data and pending reviews
      await Promise.all([
        fetchPendingReviews()
      ]);
      
      // Don't call fetchData() immediately to avoid overwriting our health updates
      setTimeout(() => {
        fetchData();
      }, 1000);
      
    } catch (err) {
      console.error("Error reviewing maintenance:", err);
      showAlert(err?.response?.data?.detail || "Failed to complete review.", 'error');
    }
  };


  const filteredEquipments = equipments.filter(([id, type, mfg, loc]) => {
    const matchesType = !filters.type || type === filters.type;
    const matchesLocation = !filters.location || loc === filters.location;
    const matchesHealth = !filters.health || (healthMap[id]?.label === filters.health);
    return matchesType && matchesLocation && matchesHealth;
  });

  return (
  <div className="flex min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
    {/* Modern Sidebar with Consistent Dark Theme */}
    <div className="w-72 bg-gradient-to-br from-slate-800 via-blue-800 to-indigo-900 border-r border-slate-600 min-h-screen shadow-2xl hidden sm:block fixed left-0 top-0 z-40 overflow-y-auto">
      <div className="p-6">
        {/* User Avatar & Welcome */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-400 via-cyan-400 to-blue-300 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-xl">
            <span className="text-2xl font-bold text-white">
              {profile.name ? profile.name.charAt(0).toUpperCase() : 'U'}
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mb-1">Welcome back!</h2>
          <p className="text-sm text-cyan-200 font-medium">{profile.name}</p>
        </div>
        
        {/* User Info Cards */}
        <div className="space-y-4 mb-8">
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20 shadow-sm hover:bg-white/15 transition-all duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-cyan-200 uppercase tracking-wide mb-1">Role</p>
                <p className="text-sm font-medium text-white capitalize">{profile.role}</p>
              </div>
              <div className="w-10 h-10 bg-gradient-to-br from-cyan-400 to-blue-600 rounded-xl flex items-center justify-center shadow-md">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
            </div>
          </div>
          
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20 shadow-sm hover:bg-white/15 transition-all duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-emerald-200 uppercase tracking-wide mb-1">Department</p>
                <p className="text-sm font-medium text-white">{profile.department}</p>
              </div>
              <div className="w-10 h-10 bg-gradient-to-br from-emerald-400 to-green-600 rounded-xl flex items-center justify-center shadow-md">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
            </div>
          </div>
          
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20 shadow-sm hover:bg-white/15 transition-all duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-blue-200 uppercase tracking-wide mb-1">Experience</p>
                <p className="text-sm font-medium text-white">{profile.experience_years} years</p>
              </div>
              <div className="w-10 h-10 bg-gradient-to-br from-blue-400 to-indigo-600 rounded-xl flex items-center justify-center shadow-md">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
            </div>
          </div>
          
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20 shadow-sm hover:bg-white/15 transition-all duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-orange-200 uppercase tracking-wide mb-1">Personnel ID</p>
                <p className="text-sm font-medium text-white">{profile.personnel_id}</p>
              </div>
              <div className="w-10 h-10 bg-gradient-to-br from-orange-400 to-yellow-600 rounded-xl flex items-center justify-center shadow-md">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V4a2 2 0 114 0v2m-4 0a2 2 0 104 0m-4 0v2" />
                </svg>
              </div>
            </div>
          </div>
        </div>
        
        {/* Logout Button - Matching Home.jsx Style */}
        <button 
          onClick={logout} 
          className="group relative w-full inline-flex items-center justify-center px-8 py-4 text-lg font-semibold text-white bg-gradient-to-r from-blue-600 to-cyan-600 rounded-2xl shadow-2xl hover:shadow-blue-500/25 transform hover:scale-105 transition-all duration-300 ease-out"
        >
          <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-blue-700 to-cyan-700 rounded-2xl blur opacity-0 group-hover:opacity-75 transition duration-300"></span>
          <span className="relative flex items-center space-x-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span>Logout</span>
          </span>
        </button>
      </div>
    </div>

    {/* Main Content with White Background */}
    <div className="flex-1 p-8 bg-white min-h-screen ml-72">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Healthcare Equipment Management System</h1>
        <p className="text-gray-600">Monitor, schedule, and manage hospital equipment maintenance</p>
      </div>
      
      {/* Alert Component */}
      {alert.show && (
        <div className={`fixed top-6 right-6 z-50 p-4 rounded-xl shadow-2xl max-w-md border-l-4 backdrop-blur-sm ${
          alert.type === 'success' ? 'bg-green-50/95 border-green-500 text-green-800' :
          alert.type === 'warning' ? 'bg-yellow-50/95 border-yellow-500 text-yellow-800' :
          alert.type === 'error' ? 'bg-red-50/95 border-red-500 text-red-800' :
          'bg-blue-50/95 border-blue-500 text-blue-800'
        }`}>
          <div className="flex justify-between items-start">
            <div className="flex">
              <div className="flex-shrink-0 mr-3">
                {alert.type === 'success' && <span className="text-green-500 text-lg">✓</span>}
                {alert.type === 'warning' && <span className="text-yellow-500 text-lg">⚠</span>}
                {alert.type === 'error' && <span className="text-red-500 text-lg">✗</span>}
                {alert.type === 'info' && <span className="text-blue-500 text-lg">ℹ</span>}
              </div>
              <p className="text-sm font-medium">{alert.message}</p>
            </div>
            <button
              onClick={() => setAlert({ show: false, message: '', type: '' })}
              className="ml-4 text-gray-400 hover:text-gray-600 text-xl leading-none"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* EDA Image - Properly Contained */}
      {edaImageBase64 && (
        <div className="mb-8 bg-white rounded-xl shadow-lg overflow-hidden">
          <img 
            src={`data:image/png;base64,${edaImageBase64}`} 
            alt="Equipment Data Analysis Dashboard" 
            className="w-full h-auto object-contain"
            style={{ maxHeight: '500px' }}
          />
        </div>
      )}

      {/* Pending Reviews Alert */}
      {pendingReviews.length > 0 && (
        <div className="bg-gradient-to-r from-yellow-50/95 to-orange-50/95 backdrop-blur-sm border border-yellow-200 rounded-2xl p-6 mb-8 shadow-sm">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center">
              <div className="w-10 h-10 bg-gradient-to-r from-yellow-400 to-orange-500 rounded-full flex items-center justify-center mr-3">
                <span className="text-white font-bold">{pendingReviews.length}</span>
              </div>
              <div>
                <h3 className="font-semibold text-yellow-800">Pending Reviews</h3>
                <p className="text-yellow-700 text-sm">Maintenance tasks awaiting review</p>
              </div>
            </div>
            <button 
              onClick={() => setTab('logs')}
              className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white px-4 py-2 rounded-xl hover:from-yellow-600 hover:to-orange-600 transition-colors font-medium"
            >
              Review Tasks
            </button>
          </div>
          
          <div className="space-y-3">
            {pendingReviews.slice(0, 3).map((review) => (
              <div key={review.maintenance_id} className="bg-white/80 backdrop-blur-sm p-4 rounded-xl shadow-sm border border-yellow-100">
                <div className="flex justify-between items-center">
                  <div className="grid grid-cols-3 gap-4 text-sm flex-1">
                    <div>
                      <p className="text-gray-500">Equipment</p>
                      <p className="font-medium">{review.equipment_id}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Technician</p>
                      <p className="font-medium">{review.technician_id}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Date</p>
                      <p className="font-medium">{review.date}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setReviewData(review);
                      setShowReviewModal(true);
                    }}
                    className="bg-gradient-to-r from-blue-600 to-cyan-600 text-white px-3 py-2 rounded-lg text-sm hover:from-blue-700 hover:to-cyan-700 transition-colors ml-4"
                  >
                    Review
                  </button>
                </div>
              </div>
            ))}
            
            {pendingReviews.length > 3 && (
              <p className="text-sm text-yellow-700 text-center pt-2">
                ...and {pendingReviews.length - 3} more tasks pending review
              </p>
            )}
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex space-x-2 mb-8">
        {[
          { key: 'equipment', label: 'Equipment Overview' },
          { key: 'logs', label: 'Maintenance Logs' },
          { key: 'users', label: 'User Management' }
        ].map(({ key, label }) => (
          <button 
            key={key} 
            onClick={() => setTab(key)} 
            className={`flex items-center px-6 py-3 font-semibold rounded-xl transition-all duration-300 ${
              tab === key 
                ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-lg' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Equipment Tab */}
      {tab === 'equipment' && (
        <div>
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">Equipment Management</h2>
            <button 
              onClick={() => setShowAddEquipment(!showAddEquipment)} 
              className="bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-all duration-300 shadow-lg"
            >
              + Add Equipment
            </button>
          </div>

          {/* Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            {[
              { field: 'type', label: 'Filter by Type' },
              { field: 'location', label: 'Filter by Location' },
              { field: 'health', label: 'Filter by Health', options: ['High Risk', 'Healthy'] }
            ].map(({ field, label, options }) => (
              <select 
                key={field} 
                className="p-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white" 
                value={filters[field]} 
                onChange={e => setFilters({ ...filters, [field]: e.target.value })}
              >
                <option value="">{label}</option>
                {options ? options.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                )) : [...new Set(equipments.map(eq => eq[field === 'type' ? 1 : 3]))].map(v => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            ))}
          </div>

          {/* Add Equipment Form */}
          {showAddEquipment && (
            <div className="bg-gray-50 p-6 rounded-2xl mb-6 border border-gray-200">
              <h3 className="font-semibold mb-4 text-gray-800">Add New Equipment</h3>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(equipmentForm).map(([k, v]) => (
                  <input 
                    key={k} 
                    placeholder={k.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} 
                    value={v} 
                    onChange={e => setEquipmentForm({ ...equipmentForm, [k]: e.target.value })} 
                    className="border border-gray-300 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white" 
                  />
                ))}
                <button 
                  onClick={handleAddEquipment} 
                  className="col-span-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white py-3 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-colors"
                >
                  Add Equipment
                </button>
              </div>
            </div>
          )}

          {/* Equipment List */}
          <div className="space-y-4">
            {filteredEquipments.sort((a, b) => a[0].localeCompare(b[0])).map(([id, type, mfg, loc, crit, date]) => (
              <div key={id} className="bg-white p-6 shadow-lg rounded-2xl border border-gray-100 hover:shadow-xl transition-shadow duration-300">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center mb-2">
                      <h3 className="text-lg font-bold text-gray-800 mr-3">{id}</h3>
                      {getBadge(id)}
                    </div>
                    <p className="text-gray-600 mb-1">{type} • {mfg}</p>
                    <p className="text-sm text-gray-500">{loc} • Installed: {date}</p>
                  </div>
                  
                  <div className="flex space-x-3">
                    <button 
                      onClick={() => navigate(`/equipment/${id}`)} 
                      className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors font-medium border border-gray-300"
                    >
                      Details
                    </button>
                    
                    {scheduledMap[id] ? (
                      <span className="px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white font-medium rounded-lg">
                        Scheduled
                      </span>
                    ) : (
                      <button
                        onClick={() => {
                          setSelectedEquipmentId(selectedEquipmentId === id ? null : id);
                          setSelectedDate(new Date());
                          setIssueDescription('');
                        }}
                        className="bg-gradient-to-r from-blue-600 to-cyan-600 text-white px-4 py-2 rounded-lg hover:from-blue-700 hover:to-cyan-700 transition-colors font-medium"
                      >
                        Schedule
                      </button>
                    )}
                    
                    <button 
                      onClick={() => setConfirmDialog({ show: true, type: 'equipment', id })} 
                      className="bg-gradient-to-r from-red-600 to-red-700 text-white px-4 py-2 rounded-lg hover:from-red-700 hover:to-red-800 transition-colors font-medium"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {selectedEquipmentId === id && (
                  <div className="mt-6 pt-6 border-t border-gray-200">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <div>
                        <Calendar
                          onChange={setSelectedDate}
                          value={selectedDate}
                          className="rounded-xl border-none shadow-sm bg-white"
                        />
                      </div>
                      <div>
                        <textarea
                          placeholder="Describe the maintenance issue..."
                          value={issueDescription}
                          onChange={(e) => setIssueDescription(e.target.value)}
                          rows={6}
                          className="w-full border border-gray-300 p-4 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                        />
                        <button
                          className="w-full mt-4 bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-colors"
                          onClick={async () => {
                            if (!selectedDate || !issueDescription) {
                              showAlert("Please select a date and provide an issue description.");
                              return;
                            }

                            try {
                              const res = await axios.put(
                                `http://localhost:8000/maintenance-log/schedule/${id}`,
                                {
                                  maintenance_type: "Preventive",
                                  date: selectedDate.toISOString().split("T")[0],
                                  issue_description: issueDescription,
                                },
                                {
                                  headers: {
                                    Authorization: `Bearer ${token}`,
                                  },
                                }
                              );

                              showAlert(res.data.message || "Maintenance scheduled successfully.");
                              setSelectedEquipmentId(null);
                              setIssueDescription('');
                              
                              setScheduledMap(prev => ({ ...prev, [id]: true }));
                              await fetchData();
                              
                            } catch (err) {
                              console.error(err);
                              showAlert(err?.response?.data?.detail || "Failed to schedule maintenance.");
                            }
                          }}
                        >
                          Confirm Schedule
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Maintenance Logs Tab */}
      {tab === 'logs' && (
        <div>
          <h2 className="text-2xl font-bold text-gray-800 mb-6">Maintenance Logs</h2>
          <MaintenanceLogs />
        </div>
      )}

      {/* Users Tab */}
      {tab === 'users' && (
        <div>
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">User Management</h2>
            <button 
              onClick={() => setShowAddUser(!showAddUser)} 
              className="bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-all duration-300 shadow-lg"
            >
              + Add User
            </button>
          </div>

          {/* Add User Form */}
          {showAddUser && (
            <div className="bg-gray-50 p-6 rounded-2xl mb-6 border border-gray-200">
              <h3 className="font-semibold mb-4 text-gray-800">Add New User</h3>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(userForm).map(([k, v]) => (
                  <input 
                    key={k} 
                    placeholder={k.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} 
                    value={v} 
                    type={k === 'password' ? 'password' : 'text'}
                    onChange={e => setUserForm({ ...userForm, [k]: e.target.value })} 
                    className="border border-gray-300 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white" 
                  />
                ))}
                <button 
                  onClick={handleAddUser} 
                  className="col-span-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white py-3 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-colors"
                >
                  Add User
                </button>
              </div>
            </div>
          )}

          {/* Users List */}
          <div className="space-y-4">
            {users.map((user) => (
              <div key={user[0]} className="bg-white p-6 shadow-lg rounded-2xl border border-gray-100">
                <div className="flex justify-between items-start">
                  <div className="grid grid-cols-2 lg:grid-cols-3 gap-6 flex-1">
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Personnel ID</p>
                      <p className="font-semibold text-gray-800">{user[0]}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Name</p>
                      <p className="font-semibold text-gray-800">{user[1]}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Role</p>
                      <p className="font-semibold text-gray-800 capitalize">{user[2]}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Department</p>
                      <p className="font-semibold text-gray-800">{user[3]}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Experience</p>
                      <p className="font-semibold text-gray-800">{user[4]} years</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setConfirmDialog({ show: true, type: 'user', id: user[0] })} 
                    className="bg-gradient-to-r from-red-600 to-red-700 text-white px-4 py-2 rounded-lg hover:from-red-700 hover:to-red-800 transition-colors font-medium ml-6"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {confirmDialog.show && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
          <div className="bg-white p-8 rounded-2xl shadow-2xl text-center max-w-md mx-4">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-red-600 text-2xl">⚠</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-800 mb-2">Confirm Deletion</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete <strong>{confirmDialog.type}</strong> <code className="bg-gray-100 px-2 py-1 rounded">{confirmDialog.id}</code>?
            </p>
            <div className="flex justify-center gap-4">
              <button 
                onClick={handleDelete} 
                className="bg-gradient-to-r from-red-600 to-red-700 text-white px-6 py-2 rounded-xl font-semibold hover:from-red-700 hover:to-red-800 transition-colors"
              >
                Yes, Delete
              </button>
              <button 
                onClick={() => setConfirmDialog({ show: false, type: '', id: '' })} 
                className="bg-gray-200 text-gray-700 px-6 py-2 rounded-xl font-semibold hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Post-Maintenance Review Modal */}
      {showReviewModal && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-screen overflow-y-auto">
            <div className="p-8">
              <h2 className="text-2xl font-bold mb-6 text-gray-800">
                Post-Maintenance Review
              </h2>
              
              {/* Maintenance Details */}
              <div className="bg-gray-50 p-6 rounded-xl mb-6">
                <h3 className="font-semibold mb-4 text-gray-800">Maintenance Details</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500 mb-1">Equipment ID</p>
                    <p className="font-semibold">{reviewData.equipment_id}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Date</p>
                    <p className="font-semibold">{reviewData.date}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Technician</p>
                    <p className="font-semibold">{reviewData.technician_id}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Maintenance ID</p>
                    <p className="font-semibold">{reviewData.maintenance_id}</p>
                  </div>
                  {reviewData.downtime_hours && (
                    <div>
                      <p className="text-gray-500 mb-1">Downtime</p>
                      <p className="font-semibold">{reviewData.downtime_hours} hours</p>
                    </div>
                  )}
                  {reviewData.cost_inr && (
                    <div>
                      <p className="text-gray-500 mb-1">Cost</p>
                      <p className="font-semibold">₹{reviewData.cost_inr}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Review Fields */}
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-3">
                    Service Rating
                  </label>
                  <select
                    value={serviceRating}
                    onChange={(e) => setServiceRating(e.target.value)}
                    className="w-full border border-gray-300 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                  >
                    <option value="">Select Rating</option>
                    <option value="1">⭐ (1 - Poor)</option>
                    <option value="2">⭐⭐ (2 - Fair)</option>
                    <option value="3">⭐⭐⭐ (3 - Good)</option>
                    <option value="4">⭐⭐⭐⭐ (4 - Very Good)</option>
                    <option value="5">⭐⭐⭐⭐⭐ (5 - Excellent)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-3">
                    Completion Status
                  </label>
                  <select
                    value={completionStatus}
                    onChange={(e) => setCompletionStatus(e.target.value)}
                    className="w-full border border-gray-300 rounded-xl p-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                  >
                    <option value="">Select Status</option>
                    <option value="Approved">Approved - Work Satisfactory</option>
                    <option value="Requires Follow-up">Requires Follow-up - Additional Work Needed</option>
                    <option value="Rejected">Rejected - Work Unsatisfactory</option>
                  </select>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-4 mt-8">
                <button
                  onClick={() => {
                    setShowReviewModal(false);
                    setServiceRating('');
                    setCompletionStatus('');
                    setReviewData({});
                  }}
                  className="px-6 py-3 bg-gray-200 text-gray-700 rounded-xl font-semibold hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleReviewMaintenance(reviewData.maintenance_id)}
                  className="px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-colors"
                >
                  Complete Review
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Schedule Form Modal */}
      {scheduleForm.show && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full">
            <div className="p-6">
              <h2 className="text-xl font-bold mb-6 text-gray-800">
                Schedule Maintenance for {scheduleForm.id}
              </h2>
              <div className="space-y-4">
                <select 
                  value={scheduleForm.maintenance_type} 
                  onChange={e => setScheduleForm({ ...scheduleForm, maintenance_type: e.target.value })} 
                  className="border border-gray-300 p-3 w-full rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                >
                  <option value="">Select Maintenance Type</option>
                  <option value="Preventive">Preventive</option>
                  <option value="Corrective">Corrective</option>
                  <option value="Calibration">Calibration</option>
                  <option value="Inspection">Inspection</option>
                </select>
                <select 
                  value={scheduleForm.technician_id} 
                  onChange={e => setScheduleForm({ ...scheduleForm, technician_id: e.target.value })} 
                  className="border border-gray-300 p-3 w-full rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
                >
                  <option value="">Select Technician</option>
                  {users.filter(user => user[2] === 'technician').map(user => (
                    <option key={user[0]} value={user[0]}>{user[1]}</option>
                  ))}
                </select>
                <input 
                  type="date" 
                  value={scheduleForm.date} 
                  onChange={e => setScheduleForm({ ...scheduleForm, date: e.target.value })} 
                  className="border border-gray-300 p-3 w-full rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white" 
                />
                <textarea 
                  placeholder="Issue Description" 
                  value={scheduleForm.issue_description} 
                  onChange={e => setScheduleForm({ ...scheduleForm, issue_description: e.target.value })} 
                  className="border border-gray-300 p-3 w-full rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white" 
                  rows={3} 
                />
                <div className="flex justify-end gap-3 pt-4">
                  <button 
                    onClick={() => setScheduleForm({ show: false, id: '', maintenance_type: '', technician_id: '', date: '', issue_description: '' })} 
                    className="bg-gray-200 text-gray-700 px-6 py-2 rounded-xl font-semibold hover:bg-gray-300 transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handleSchedule} 
                    className="bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-2 rounded-xl font-semibold hover:from-green-700 hover:to-emerald-700 transition-colors"
                  >
                    Schedule
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  </div>
);
}
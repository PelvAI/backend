from app.db.session import Base
from app.models.user import User, Profile, Organization, Team, Affiliation, ProfessionalLink, AuditLog, DeletionRequest
from app.models.education import EducationModule
from app.models.clinical import (
    ClinicalForm, FormSection, FormQuestion, ScoringLogic, 
    UserSubmission, SubmissionAnswer, ClinicalSnapshot,
    AnswerOption, ScoringRule, ClinicalAlert, Target, ProfileTarget
)
from app.models.training import Exercise, SessionTemplate, UserAssignment, SessionPerformance
from app.models.gamification import Season, Currency, Wallet, Transaction, ShopItem, UserInventory, UserStreak
from app.models.recommendations import RecommendationRule
from app.models.system import SystemSetting, Translation
from app.models.map import LearningPath, PathNode, NodeContent, NodeRequirement, UserPathProgress
from app.models.ai import AIConversation, AIMessage, AIRagSource, AIOptimization, OptimizationFeedback
from app.models.business import SubscriptionPlan, UserSubscription, AdCampaign, AdPlacement

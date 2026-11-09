'use server'

import { cookies } from 'next/headers'
import { prisma } from '@/lib/prisma'

export async function createSession(token) {
  const cookieStore = await cookies()
  cookieStore.set('auth-token', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60 * 24 * 7, // 1 week
    path: '/',
  })
}

export async function removeSession() {
  const cookieStore = await cookies()
  cookieStore.delete('auth-token')
}

export async function syncDatabaseUser({ uid, email, displayName, photoURL }) {
  if (!uid || !email) return null;
  
  try {
    const user = await prisma.user.upsert({
      where: { firebaseId: uid },
      update: {
        name: displayName,
        photoUrl: photoURL,
      },
      create: {
        firebaseId: uid,
        email: email,
        name: displayName,
        photoUrl: photoURL,
      }
    });
    
    return user;
  } catch (error) {
    console.error("Error syncing user to database:", error);
    return null;
  }
}
